import os
import sys
import re
import json
import time
import requests
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AutonomousMasterclassEngine")

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
CONFIG_DIR = os.path.join(SCRIPT_DIR, "config")
SEEDS_PATH = os.path.join(CONFIG_DIR, "academic_seeds.json")
HISTORY_DIR = os.path.join(SCRIPT_DIR, "history")
os.makedirs(HISTORY_DIR, exist_ok=True)
EVERGREEN_HISTORY_PATH = os.path.join(HISTORY_DIR, "evergreen_content_history.json")

from shared.supabase_client import SupabaseBlogClient
from shared.telegram import send_admin_alert, broadcast_public_telegram_post, resolve_clean_article_url
from shared.drive_image_sanitizer import resolve_editorial_image
from shared.google_sheet_queue import fetch_pending_editorial_row, mark_editorial_row_published
from shared.exam_logo_registry import generate_exam_vector_banner
from shared.blog_linter import DomainAdaptiveMasterclassAuditor

try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None

GEMINI_API_KEY = (
    os.getenv("GEMINI_API_KEY") or
    os.getenv("VITE_GEMINI_API_KEY") or
    ""
).strip('"')

DEEPSEEK_API_KEY = (
    os.getenv("DEEPSEEK_API_KEY") or
    os.getenv("NVIDIA_NEMOTRON_KEY") or
    os.getenv("NVIDIA_NIM_API_KEY") or
    os.getenv("OPENAI_API_KEY") or
    ""
)

# ==============================================================================
# 6 EDITORIAL ARCHETYPES CLASSIFIER
# ==============================================================================
def classify_editorial_archetype(title: str, focus_notes: str = "", category: str = "") -> str:
    combined = f"{title} {focus_notes} {category}".lower()
    if any(k in combined for k in ["salary", "pay scale", "grade pay", "in-hand", "in hand", "allowances", "promotion", "hierarchy", "remuneration"]):
        return "SALARY_PROFILE"
    elif any(k in combined for k in ["job profile", "life of", "routine", "posting", "powers", "lifestyle", "duties", "work life", "responsibilities"]):
        return "LIFESTYLE_ROUTINE"
    elif any(k in combined for k in ["strategy", "roadmap", "how to prepare", "from scratch", "beginner", "timetable", "time table", "without coaching", "self study"]):
        return "STRATEGY_ROADMAP"
    elif any(k in combined for k in ["books", "booklist", "study material", "best books", "notes", "resources", "reference books"]):
        return "BOOKLIST_RESOURCES"
    elif any(k in combined for k in ["cut off", "cutoff", "safe score", "analysis", "marks", "trend", "safe attempts", "scorecard"]):
        return "CUTOFF_ANALYSIS"
    else:
        return "SUBJECT_SHORTCUTS"

# 35+ HIGH-YIELD CURRICULUM TAXONOMY (Autonomous Fallback Wheel)
UNIVERSAL_ENGAGING_TOPICS = [
    {
        "category": "Exam Strategy",
        "topic": "OSSC CGL In-Hand Salary, Grade Pay, Allowances & 10-Year Promotion Hierarchy",
        "framework": "7th Pay Commission Pay Matrix & Allowances",
        "focus": "Detailed basic pay, DA, HRA, NPS take-home pay, perks, job responsibilities, and promotional hierarchy ladder."
    },
    {
        "category": "Exam Strategy",
        "topic": "Life of an Odisha Police Sub-Inspector (SI): Daily Routine, Postings, Powers & Challenges",
        "framework": "Field Operations & Career Lifestyle Overview",
        "focus": "A day in the life of a Police SI, district postings, powers, operational jurisdiction, leave policy, and career prestige."
    },
    {
        "category": "Exam Strategy",
        "topic": "How to Crack OPSC OAS Prelims from Scratch Without Coaching: The 6-Month Roadmap",
        "framework": "Self-Study Strategy & Resource Blueprint",
        "focus": "Syllabus foundation, high-yield topic weightage, daily 6-hour timetable, and mock test revision routine."
    },
    {
        "category": "Exam Strategy",
        "topic": "Best Standard Books for Odisha Govt Exams Recommended by Previous Toppers",
        "framework": "Subject-Wise Booklist & Resource Alignment",
        "focus": "Standard textbooks for Odia Grammar, GS, Quant, Reasoning, and English with chapter reading guidelines."
    },
    {
        "category": "Quantitative Aptitude",
        "topic": "Alligation & Mixture Shortcut Algorithms to Solve in 20 Seconds",
        "framework": "The Cross-Difference Ratio Method",
        "focus": "Solving weighted average, replacement of liquids, and multi-vessel mixture problems without algebra equations."
    },
    {
        "category": "Quantitative Aptitude",
        "topic": "Time, Speed & Distance: Train Crossing & Relative Speed Traps Solved Fast",
        "framework": "The Relative Velocity & Unit Conversion Matrix",
        "focus": "Eliminating m/s to km/h conversion traps, moving platform crossings, and circular track overtaking."
    },
    {
        "category": "Data Interpretation",
        "topic": "Missing DI & Caselet Data Extraction Frameworks for State Selection Exams",
        "framework": "The Variable Interlocking Matrix",
        "focus": "Structuring unorganized paragraph data into clean tabular forms and solving in under 2 minutes."
    }
]

def load_json_file(file_path: str, default_val: Any = None) -> Any:
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"⚠️ Error reading JSON from {file_path}: {e}")
    return default_val if default_val is not None else []

def save_json_file(file_path: str, data: Any):
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"❌ Error saving JSON to {file_path}: {e}")

def call_ai_api(messages: list, temperature: float = 0.3) -> Tuple[str, str, bool]:
    # TIER 1 (PRIMARY): Google AI Studio Gemini API
    # Gemini is always prioritized with retry-with-backoff on 429/503 before any fallback.
    gemini_last_err = ""
    GEMINI_MODELS = ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.6-flash", "gemini-3.7-flash", "gemini-3.8-flash", "gemini-3.1-flash-lite"]
    if GEMINI_API_KEY:
        gemini_prompt = "\n\n".join([f"Role: {m.get('role')}\n{m.get('content')}" for m in messages])
        for g_model in GEMINI_MODELS:
            max_model_attempts = 2
            for attempt in range(1, max_model_attempts + 1):
                try:
                    logger.info(f"🚀 [SEOBlogEngine] Calling Gemini ({g_model}) attempt {attempt}...")
                    g_url = f"https://generativelanguage.googleapis.com/v1beta/models/{g_model}:generateContent?key={GEMINI_API_KEY}"
                    g_payload = {
                        "contents": [{"parts": [{"text": gemini_prompt}]}],
                        "generationConfig": {
                            "temperature": temperature,
                            "maxOutputTokens": 8192
                        }
                    }
                    g_res = requests.post(g_url, headers={"Content-Type": "application/json"}, json=g_payload, timeout=40)
                    if g_res.ok:
                        data = g_res.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                            if "</think>" in content:
                                content = content.split("</think>")[-1].strip()
                            if content and content.strip():
                                logger.info(f"✅ [Google Gemini - {g_model}] Blog content generated successfully as Primary.")
                                return content, f"Google Gemini ({g_model}) [Primary]", False
                    elif g_res.status_code == 429:
                        gemini_last_err = f"{g_model}: HTTP 429 quota"
                        if attempt < max_model_attempts:
                            import time as _t
                            logger.info(f"⏳ [Google Gemini - {g_model}] HTTP 429 quota — waiting 65s for quota reset...")
                            _t.sleep(65)
                            continue
                        else:
                            logger.warning(f"⚠️ [Google Gemini - {g_model}] Quota exhausted after retry. Trying next model...")
                    elif g_res.status_code == 503:
                        gemini_last_err = f"{g_model}: HTTP 503 high demand"
                        if attempt < max_model_attempts:
                            import time as _t
                            logger.info(f"⏳ [Google Gemini - {g_model}] HTTP 503 high demand — waiting 30s then retrying...")
                            _t.sleep(30)
                            continue
                        else:
                            logger.warning(f"⚠️ [Google Gemini - {g_model}] Still busy after retry. Trying next model...")
                    else:
                        gemini_last_err = f"{g_model}: HTTP {g_res.status_code} - {g_res.text[:100]}"
                        logger.warning(f"⚠️ [Google Gemini - {g_model}] HTTP {g_res.status_code}. Trying next model...")
                    break
                except Exception as g_err:
                    gemini_last_err = f"{g_model}: {g_err}"
                    logger.warning(f"⚠️ [Google Gemini - {g_model}] failed: {g_err}. Trying next model...")
                    break

        logger.warning(f"⚠️ [SEOBlogEngine] All Gemini models exhausted. Transitioning to NVIDIA NIM as last resort...")

    api_key = DEEPSEEK_API_KEY
    if not api_key:
        raise ValueError("Neither GEMINI_API_KEY nor DEEPSEEK_API_KEY found.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    models_to_try = [
        ("nvidia/nemotron-3-super-120b-a12b", "https://integrate.api.nvidia.com/v1/chat/completions", False),
        ("z-ai/glm-5.3", "https://integrate.api.nvidia.com/v1/chat/completions", False),
        ("meta/llama-3.2-11b-vision-instruct", "https://integrate.api.nvidia.com/v1/chat/completions", False)
    ]
    native_deepseek_key = (os.getenv("DEEPSEEK_API_KEY") or "").strip('"')
    if native_deepseek_key.startswith("sk-"):
        models_to_try.append(("deepseek-chat", "https://api.deepseek.com/v1/chat/completions", False))

    for model_name, endpoint, is_r1 in models_to_try:
        try:
            payload = {
                "model": model_name,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": 4096
            }
            res = requests.post(endpoint, headers=headers, json=payload, timeout=45)
            if res.ok:
                resp_json = res.json()
                content = resp_json["choices"][0]["message"]["content"]
                if "</think>" in content:
                    content = content.split("</think>")[-1].strip()
                try:
                    from shared.telegram import send_ai_fallback_notification
                    send_ai_fallback_notification(
                        engine="seo_blog_engine (Strategy & Guidance Blog)",
                        primary_error=gemini_last_err or "Gemini models exhausted",
                        fallback_model=model_name
                    )
                except Exception as alert_err:
                    logger.warning(f"⚠️ [Alert Failed]: {alert_err}")
                return content, model_name, True
        except Exception as ex:
            logger.warning(f"⚠️ AI model {model_name} attempt failed: {ex}")
            continue

    raise RuntimeError("All AI models failed.")

def research_topic(topic: str, category: str, framework: str) -> List[str]:
    snippets = []
    queries = [
        f"{topic} {category} Odisha exam",
        f"{topic} syllabus tricks guide",
        f"{topic} previous year questions"
    ]
    if DDGS:
        try:
            ddgs = DDGS()
            for q in queries:
                try:
                    results = list(ddgs.text(q, max_results=3))
                    for r in results:
                        snippets.append(f"{r.get('title')}: {r.get('body')}"[:260])
                except Exception:
                    pass
        except Exception:
            pass
    return snippets[:6]

def build_intent_adaptive_prompts(
    topic_name: str,
    category: str,
    focus_notes: str,
    research_data: list,
    feedback_prompt: str = ""
) -> Tuple[str, str]:
    """
    Builds a tailored, intent-adaptive prompt based on the 6 Editorial Archetypes.
    """
    archetype = classify_editorial_archetype(topic_name, focus_notes, category)
    logger.info(f"🧠 Detected Editorial Archetype: '{archetype}' for topic '{topic_name}'")

    if archetype == "SALARY_PROFILE":
        archetype_instructions = """
======================================================================
EDITORIAL MANDATE: SALARY, PERKS & PROMOTION HIERARCHY GUIDE
======================================================================
1. OFFICIAL SCALE OF PAY GROUNDING (ORSP RULES 2017 & 7TH PAY COMMISSION):
   - Ground all salary figures strictly in the official Odisha Revised Scales of Pay (ORSP) Rules, 2017.
   - For Group B (OSSC CGL, Sub-Inspector): Level-9 (Cell 1: ₹35,400 to ₹1,12,400) or Level-10 (Cell 1: ₹44,900 to ₹1,42,400).
   - For Group A (OPSC OAS / OFS): Level-12 (Cell 1: ₹56,100 to ₹1,77,500).
   - Dearness Allowance (DA): Apply prevailing state rate (50%+).
   - House Rent Allowance (HRA): 18% for Bhubaneswar/Cuttack, 9% for other district headquarters.
   - Zero-Hallucination: Do NOT quote obsolete 6th Pay Commission grade pays or fabricated numbers.
2. IN-HAND TAKE-HOME SALARY CALCULATION HTML TABLE:
   - Provide a clean <table> with columns: Component | Percentage / Calculation | Amount (₹).
   - Rows: Basic Pay, DA, HRA, Medical Allowance, Gross Salary, NPS Employee Tier-1 (10% of Basic+DA), Professional Tax (₹200), Net In-Hand Take-Home Salary.
3. ALLOWANCES & GOVERNMENT BENEFITS (Government quarters entitlement, medical reimbursement under OSTF, travel concessions).
4. 10-YEAR CAREER GROWTH & PROMOTION HIERARCHY TREE (Entry Cadre -> Senior Assistant / Section Officer / DSP / Joint Secretary -> Departmental exam criteria).
5. JOB PROFILE & DAILY RESPONSIBILITIES (Office administration, field inspections, public grievance handling, reporting hierarchy).
6. 4 FREQUENTLY ASKED QUESTIONS (Probation period pay policy, yearly increment of 3%, NPS vs GPF).
"""
    elif archetype == "LIFESTYLE_ROUTINE":
        archetype_instructions = """
======================================================================
EDITORIAL MANDATE: JOB PROFILE, LIFESTYLE & WORK CULTURE OVERVIEW
======================================================================
1. ROLE OVERVIEW & PRESTIGE in the government department / administration.
2. A DAY IN THE LIFE: Realistic morning-to-evening schedule, shift rotations, and core operational responsibilities.
3. FIELD VS. OFFICE POSTINGS & DISTRICT TRANSFER POLICIES across Odisha.
4. POWERS, AUTHORITY & REAL-WORLD CHALLENGES on the ground.
5. WORK-LIFE BALANCE, LEAVE POLICIES & CAREER SATISFACTION.
6. 4 PRACTICAL CANDIDATE FAQS (Accommodation, training academy routine, career perks).
"""
    elif archetype == "STRATEGY_ROADMAP":
        archetype_instructions = """
======================================================================
EDITORIAL MANDATE: COMPLETE EXAM PREPARATION BLUEPRINT & TIMETABLE
======================================================================
1. PHASE 1: Syllabus Foundation & Concept Clarity (Week 1–4).
2. PHASE 2: High-Yield Topic Weightage Matrix (HTML Table showing marks weightage per subject).
3. PHASE 3: Ideal Daily 6-Hour Timetable & Study Schedule.
4. PHASE 4: Mock Test Strategy, Sectional Speed Drills & Error-Logging Notebook Technique.
5. TOP 5 DEADLY TRAPS THAT CAUSE FAILURE & HOW TO AVOID THEM.
6. 4 STUDENT DILEMMA FAQS (Self-study vs Coaching, Working aspirants schedule, Negative marking control).
"""
    elif archetype == "BOOKLIST_RESOURCES":
        archetype_instructions = """
======================================================================
EDITORIAL MANDATE: TOPPER-RECOMMENDED STANDARD BOOKLIST & STUDY MATERIAL
======================================================================
1. SUBJECT-WISE RECOMMENDED REFERENCE BOOKS HTML TABLE:
   - Columns: Subject | Standard Textbook & Author | Recommended Practice / PYQ Book | Priority.
2. SYLLABUS MAPPING: Which specific chapters to read and which to safely skip.
3. STANDARD TEXTBOOKS VS. PYQ COMPILATIONS: The 70-30 preparation rule.
4. HOW TO READ STANDARD BOOKS EFFECTIVELY & MAKE 1-PAGE REVISION NOTES.
5. 4 FAQS ON STUDY MATERIAL (NCERTs necessity, Odia language reference books, online resources).
"""
    elif archetype == "CUTOFF_ANALYSIS":
        archetype_instructions = """
======================================================================
EDITORIAL MANDATE: PREVIOUS YEAR CUT-OFF TRENDS & SAFE SCORE TARGET
======================================================================
1. PREVIOUS YEARS CATEGORY-WISE CUT-OFF MATRIX HTML TABLE (UR, SEBC, SC, ST, Ex-Servicemen).
2. KEY DRIVING FACTORS: Vacancy trends, question difficulty index, and applicant numbers.
3. REALISTIC TARGET SCORE BLUEPRINT: Safe attempt strategy section by section.
4. IMPACT OF NEGATIVE MARKING & NORMALIZATION FORMULA.
5. 4 FAQS ON CUT-OFFS (Normalization scoring, category concessions, qualifying vs merit marks).
"""
    else:  # SUBJECT_SHORTCUTS
        archetype_instructions = """
======================================================================
EDITORIAL MANDATE: SUBJECT MASTERCLASS & 20-SECOND SHORTCUT TRICKS
======================================================================
1. CORE CONCEPT BREAKDOWN & SPEED FORMULAS (in clean LaTeX and highlighted <code> blocks).
2. AT LEAST TWO (2) FULLY SOLVED WORKED EXAMPLES in <div class="worked-example">:
   - 📌 <b>Exam Problem Scenario:</b> [Realistic competitive exam question]
   - ⚠️ <b>The Common Slow Trap:</b> [Standard school method taking 90s]
   - ⚡ <b>The 20-Second Shortcut:</b> [Topper's arithmetic method]
   - 🎯 <b>Final Verified Solution:</b> [Exact answer]
3. SPEED COMPARISON HTML TABLE (Standard Method 90s vs Shortcut 20s).
4. 'IF-THEN' 45-SECOND EXAM DAY DECISION HEURISTICS.
5. 7-DAY MICRO-PRACTICE DRILL & 4 STUDENT FAQS.
"""

    system_prompt = f"""You are the Chief Academic Mentor & Lead Content Strategist for OdishaExamPrep (https://www.odishaexamprep.in).
Your mission is to generate an ORIGINAL, HIGH-ENGAGEMENT, EXHAUSTIVE AND AUTHORITATIVE ARTICLE (1200-2200 words) for '{topic_name}'.
Adopt the voice of an elite mentor who explains concepts with crystal clarity, high energy, and zero fluff.

======================================================================
GENERAL FORMATTING RULES:
======================================================================
1. PARAGRAPH SIZING: Keep paragraphs SHORT and PUNCHY (strictly 2–3 sentences per <p>). Never write dense walls of text.
2. RICH HTML ELEMENTS: Use <h2>, <h3>, <table> with <thead> and <tbody>, <ul>, <strong> highlights, and callouts.
3. NO ELLIPSES: Never use '...' or placeholder brackets. Write complete, polished content.

{archetype_instructions}

{feedback_prompt}

Return ONLY a valid JSON object matching this schema:
{{
  "title": "{topic_name}",
  "meta_title": "SEO Title under 60 chars | OdishaExamPrep",
  "meta_description": "Engaging 150-160 char summary for Google search snippets",
  "slug": "url-friendly-slug",
  "html_content": "Full rich HTML article content",
  "keywords": "comma separated relevant keywords",
  "category": "{category}"
}}"""

    user_prompt = (
        f"Target Exam / Category: {category}\n"
        f"Article Title: {topic_name}\n"
        f"Special Focus / Creator Notes: {focus_notes or 'Comprehensive candidate-first breakdown'}\n"
        f"Research Snippets: {json.dumps(research_data, indent=2)}\n"
        f"Generate the complete, highly detailed HTML article following the exact archetype requirements."
    )

    return system_prompt, user_prompt

def main():
    logger.info("==================================================")
    logger.info("🚀 ENTERPRISE EDITORIAL MASTERCLASS ENGINE")
    logger.info("   Architecture: Google Sheet Queue + Dynamic Archetypes + Vector Fallbacks")
    logger.info("==================================================")

    supabase_client = SupabaseBlogClient()
    existing_blogs = supabase_client.fetch_all_blogs()

    # Step 1: Check Google Sheet Editorial Queue for Pending Topics
    sheet_obj, row_index, pending_row = fetch_pending_editorial_row()
    
    is_custom_editorial = False
    if pending_row and pending_row.get("title"):
        is_custom_editorial = True
        topic_name = pending_row["title"]
        category = pending_row.get("target_exam") or "Exam Strategy"
        focus_notes = pending_row.get("focus_notes", "")
        custom_image_url = pending_row.get("image_url", "")
        logger.info(f"🎯 [Editorial Queue] Processing Custom Topic: '{topic_name}' ({category})")
    else:
        logger.info("ℹ️ [Editorial Queue] No pending custom topics found. Falling back to autonomous rotation.")
        # Fallback to curriculum rotation
        day_of_year = datetime.now().timetuple().tm_yday
        topic_item = UNIVERSAL_ENGAGING_TOPICS[day_of_year % len(UNIVERSAL_ENGAGING_TOPICS)]
        topic_name = topic_item["topic"]
        category = topic_item["category"]
        focus_notes = topic_item["focus"]
        custom_image_url = ""

    # Step 2: Research & Generate Masterclass Article
    research_data = research_topic(topic_name, category, focus_notes)
    
    verified_article = None
    feedback = ""
    model_used = ""
    used_fallback = False

    for attempt in range(1, 3):
        logger.info(f"⚙️ Generation Attempt #{attempt} for '{topic_name}'...")
        sys_p, user_p = build_intent_adaptive_prompts(topic_name, category, focus_notes, research_data, feedback)

        try:
            raw_response, m_used, u_fb = call_ai_api([
                {"role": "system", "content": sys_p},
                {"role": "user", "content": user_p}
            ])

            clean_json = raw_response.strip()
            if "```json" in clean_json:
                clean_json = clean_json.split("```json")[1].split("```")[0].strip()
            elif "```" in clean_json:
                clean_json = clean_json.split("```")[1].split("```")[0].strip()

            candidate = json.loads(clean_json)
            html_content = candidate.get("html_content", "")
            title = candidate.get("title", topic_name)

            # Audit quality
            audit = DomainAdaptiveMasterclassAuditor.audit_article(html_content, title, category)
            logger.info(f"   📊 Audit Score: {audit['quality_score']}/100 | Words: {audit['word_count']}")

            if audit["is_passed"] or audit["quality_score"] >= 80:
                verified_article = candidate
                model_used = m_used
                used_fallback = u_fb
                break
            else:
                feedback = f"\nFix these issues: " + ", ".join(audit["critical_errors"] + audit["warnings"])
        except Exception as e:
            logger.error(f"❌ AI Generation Error: {e}")

    if not verified_article:
        logger.error("❌ Failed to generate verified article.")
        send_admin_alert("ENGAGEMENT_BLOG", "FAILED", {"title": topic_name, "error": "AI generation failed audit"})
        return

    # Step 3: Resolve Editorial Image (Custom Drive Link / Direct URL / High-Res Vector Banner)
    title = verified_article.get("title", topic_name)
    slug = verified_article.get("slug", re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-'))

    img_res = resolve_editorial_image(
        image_url_input=custom_image_url,
        title=title,
        category=category,
        target_exam=category,
        slug=slug
    )

    verified_article["featured_image"] = img_res["image_url"]
    verified_article["featured_image_alt"] = img_res["alt_text"]
    verified_article["photographer"] = img_res["photographer"]
    verified_article["cover_image"] = img_res.get("local_path")
    verified_article["published_at"] = datetime.now().isoformat()
    verified_article["targetExamId"] = category
    verified_article["is_published"] = True
    verified_article["status"] = "published"

    # Step 4: Insert into Supabase Database
    db_res = supabase_client.insert_blog_post(verified_article)
    if not db_res or not db_res.get("id"):
        logger.error("❌ Supabase insertion returned no ID. Skipping broadcast.")
        send_admin_alert("ENGAGEMENT_BLOG", "FAILED", {"title": title, "error": "Database insert failed or returned no ID"})
        return

    article_id = db_res.get("id")
    article_url = f"https://www.odishaexamprep.in/blog/{article_id}"
    verified_article["article_url"] = article_url
    verified_article["article_id"] = article_id

    # Step 5: Broadcast to Public Channels
    broadcast_public_telegram_post("ENGAGEMENT_BLOG", verified_article)

    # Step 6: If custom editorial from Google Sheet, mark as Published!
    if is_custom_editorial and sheet_obj and row_index:
        mark_editorial_row_published(sheet_obj, row_index, article_url)

    # Step 7: Send Admin Success Alert
    send_admin_alert("ENGAGEMENT_BLOG", "SUCCESS", verified_article)
    logger.info(f"🎉 Successfully published masterclass: '{title}' ({article_url})")

if __name__ == "__main__":
    try:
        main()
    except SystemExit as se:
        sys.exit(se.code)
    except Exception as e:
        logger.error(f"❌ Fatal SEOBlogEngine Error: {e}")
        try:
            send_admin_alert("ENGAGEMENT_BLOG", "FAILED", {"stage": "Main Runner Exception", "error": str(e)})
        except Exception:
            pass
        sys.exit(1)
