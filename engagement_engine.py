import os
import sys
import json
import time
import requests
from datetime import datetime
try:
    import gspread
    from google.oauth2.service_account import Credentials
except ImportError:
    gspread = None
    Credentials = None

try:
    from ddgs import DDGS
except ImportError:
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        DDGS = None

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "")

GEMINI_API_KEY = (
    os.getenv("GEMINI_API_KEY") or
    os.getenv("VITE_GEMINI_API_KEY") or
    ""
).strip('"')

DEEPSEEK_API_KEY = (
    os.getenv("DEEPSEEK_API_KEY") or
    os.getenv("NVIDIA_NIM_API_KEY") or
    os.getenv("OPENAI_API_KEY") or
    os.getenv("VITE_DEEPSEEK_API_KEY") or
    ""
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CREDS_FILE = os.path.join(SCRIPT_DIR, "google_credentials.json")
HISTORY_FILE = os.path.join(SCRIPT_DIR, "published_history.json")

ADMINISTRATIVE_NEWS_KEYWORDS = [
    "admit card", "vacancy", "vacancies", "result", "results", "notification",
    "recruitment", "application date", "exam date", "court", "hall ticket",
    "answer key", "cut off", "cutoff", "eligibility criteria"
]

# ---------- Daily topic rotation wheel (7 domains, cycles by day-of-year) ----------
import re

DAILY_TOPIC_WHEEL = [
    {"topic": "Mathematics",       "subtopics": "Number System, Percentage, Profit & Loss, Time & Work, Ratio & Proportion, Simplification, Averages"},
    {"topic": "Reasoning",         "subtopics": "Syllogism, Blood Relations, Coding-Decoding, Series Completion, Direction Sense, Analogy, Puzzles"},
    {"topic": "General Knowledge", "subtopics": "Indian History, Geography, Indian Polity & Constitution, Economy, Science, Art & Culture, National Symbols"},
    {"topic": "English Grammar",   "subtopics": "Tenses, Articles, Prepositions, Subject-Verb Agreement, Error Detection, Fill-in-the-blanks, Vocabulary"},
    {"topic": "Science & Tech",    "subtopics": "Physics Laws, Chemistry Reactions, Biology Concepts, Computer Basics, Space Technology, Environment & Ecology"},
    {"topic": "Odisha State GK",   "subtopics": "Odisha History, Culture & Tribes, Geography & Rivers, Economy, Government Schemes, Wildlife Sanctuaries, Districts"},
    {"topic": "Exam Strategy",     "subtopics": "Revision Planning, Mock Test Techniques, Active Recall Methods, Time Management, Weak-area Analysis, Concentration"},
]

def normalize_q(q):
    """Normalize question string for dedup comparison (strips all non-alphanumeric)."""
    return re.sub(r'[^a-z0-9]', '', q.lower()) if q else ''

def get_today_topic():
    """Return today's mandatory topic domain from the 7-day rotation wheel."""
    day_of_year = datetime.now().timetuple().tm_yday
    return DAILY_TOPIC_WHEEL[day_of_year % len(DAILY_TOPIC_WHEEL)]

def validate_engagement_quality(poll_data):
    """
    Fail-Closed Quality, Accuracy & Syllabus Gate for Engagement Engine:
    - Enforces strict Zero-False-Positive Policy (P = 1.0).
    - Enforces Quantitative Score Threshold >= 80/100.
    - Rejects generic advice ("study hard", "stay focused", "work hard", etc.)
    - Rejects administrative news/tenders/results disguised as polls.
    - Rejects unreplaced template placeholders ([Topic], [Option], etc.).
    - Rejects invalid option counts, empty options, non-unique options.
    - Rejects invalid correct_option_index or missing explanations.
    """
    if not isinstance(poll_data, dict):
        return False, "Invalid poll payload structure"

    question = str(poll_data.get("question", "")).strip()
    options = poll_data.get("options", [])
    correct_idx = poll_data.get("correct_option_index")
    explanation = str(poll_data.get("explanation", "")).strip()
    target_exam = str(poll_data.get("target_exam", "")).strip()

    if not question or len(question) < 15:
        return False, "Question is empty or too short (< 15 chars)"

    # Check 1: Template Placeholder Detection
    if re.search(r'\[(topic|exam|option|insert|name|category|question)[^\]]*\]', f"{question} {explanation} {' '.join(str(o) for o in options)}", re.IGNORECASE):
        return False, "Contains unreplaced bracketed template placeholder"

    # Check 2: Banned Generic Motivation & Administrative Noise Filter
    generic_banned = [
        "study hard", "work hard", "do your best", "stay focused", "read carefully",
        "believe in yourself", "never give up", "keep trying", "prepare well",
        "admit card", "results declared", "tender notice", "application deadline"
    ]
    q_lower = question.lower()
    exp_lower = explanation.lower()
    if any(b in q_lower or b in exp_lower for b in generic_banned):
        return False, "Rejected for generic motivational fluff or administrative noise"

    # Check 3: Strict Option Validation
    if not isinstance(options, list) or len(options) < 3 or len(options) > 5:
        return False, f"Invalid options count ({len(options) if isinstance(options, list) else 0}). Must be 3-5 options."

    clean_options = [str(opt).strip() for opt in options]
    if any(not opt for opt in clean_options):
        return False, "Contains empty option text"

    if len(set(clean_options)) != len(clean_options):
        return False, "Options contain duplicate choices"

    try:
        correct_idx = int(correct_idx)
        if correct_idx < 0 or correct_idx >= len(clean_options):
            return False, f"Invalid correct_option_index ({correct_idx}) for {len(clean_options)} options."
    except (TypeError, ValueError):
        return False, "correct_option_index is missing or not an integer"

    if not explanation or len(explanation) < 10:
        return False, "Explanation is missing or too short (< 10 chars)"

    # Check 4: Fail-Closed Quantitative Scoring (Passing Threshold >= 80/100)
    score = 0
    breakdown = []

    # Question Clarity & Character Count (+25)
    if len(question) >= 25 and "?" in question:
        score += 25
        breakdown.append("Question Clarity (+25)")

    # Option Integrity & Trap Plausibility (+25)
    if len(clean_options) in [3, 4] and all(len(o) >= 2 for o in clean_options):
        score += 25
        breakdown.append("Option Structure (+25)")

    # Syllabus Concept Grounding (+25)
    if target_exam and len(target_exam) >= 3 and not any(b in q_lower for b in generic_banned):
        score += 25
        breakdown.append("Syllabus Grounding (+25)")

    # Educational Proof & Strategy Explanation (+25)
    if len(explanation) >= 20 and len(explanation) <= 300:
        score += 25
        breakdown.append("Educational Proof (+25)")

    if score < 80:
        return False, f"REJECTED_SUB_THRESHOLD ({score}/100 < 80 -> {', '.join(breakdown)})"

    return True, f"Passed quality & accuracy checks (Score: {score}/100)"
# ----------------------------------------------------------------------------------

def load_published_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Error loading history file: {e}")
    return []

def save_published_history(history_data):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history_data, f, indent=2, ensure_ascii=False)
        print("✅ Updated published_history.json successfully.")
    except Exception as e:
        print(f"❌ Failed to save published_history.json: {e}")

def send_admin_alert(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_ADMIN_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
        res = requests.post(url, json=payload, timeout=20)
        return res.ok
    except Exception as e:
        print(f"❌ Failed to send Admin Alert: {e}")
        return False

def send_telegram_regular_poll(question, options, explanation=""):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPoll"
        print(f"[VERBOSE LOG] Sending Regular Telegram Engagement Text Poll to Channel ({TELEGRAM_CHAT_ID})...")
        
        # Telegram API regular poll payload (NO type="quiz", NO correct_option_id, NO green checkmarks)
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "question": question[:300],
            "options": json.dumps([str(opt) for opt in options]),
            "is_anonymous": True,
            "type": "regular"
        }

        res = requests.post(url, data=payload, timeout=20)
        if res.ok:
            print("✅ Regular Telegram Engagement Poll posted successfully!")
            
            # Send follow-up strategy explanation & CTA bubble with Rotational Student Photo of the Day
            if explanation:
                day_of_week = datetime.now().isoweekday() # 1 = Mon ... 7 = Sun
                student_photo_path = os.path.join(SCRIPT_DIR, f"student {day_of_week}.png")
                caption_text = (
                    f"💡 <b>Strategy Insights:</b>\n{explanation}\n\n"
                    f"🎯 <b>Practice Daily Mock Tests & Question Banks:</b>\n👉 https://www.odishaexamprep.in/\n\n"
                    f"📺 <b>Join YouTube Channel for Video Classes:</b>\n👉 https://www.youtube.com/@OdishaExamPrep365"
                )
                
                if os.path.exists(student_photo_path):
                    print(f"📷 Attaching Rotational Student Photo of the Day ({os.path.basename(student_photo_path)})...")
                    exp_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
                    with open(student_photo_path, "rb") as photo_file:
                        exp_payload = {
                            "chat_id": TELEGRAM_CHAT_ID,
                            "caption": caption_text,
                            "parse_mode": "HTML"
                        }
                        files = {"photo": photo_file}
                        requests.post(exp_url, data=exp_payload, files=files, timeout=25)
                else:
                    exp_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                    exp_payload = {
                        "chat_id": TELEGRAM_CHAT_ID,
                        "text": caption_text,
                        "parse_mode": "HTML"
                    }
                    requests.post(exp_url, data=exp_payload, timeout=15)
                print("✅ Follow-up Strategy Explanation with Student Promo Photo sent!")
            return True
        else:
            print(f"❌ Telegram sendPoll Error ({res.status_code}): {res.text}")
            return False
    except Exception as e:
        print(f"❌ Failed to send Telegram Regular Poll: {e}")
        return False

def post_to_youtube_community_poll(poll_data):
    print("[VERBOSE LOG] Posting Engagement Text Poll to YouTube Community...")
    try:
        from post_to_youtube import post_to_youtube_poll
        options = poll_data.get("options", [])
        yt_data = {
            "Target_Exam": poll_data.get("target_exam", "Daily Quiz"),
            "Question_Text": poll_data.get("question", ""),
            "Option_A": options[0] if len(options) > 0 else "A",
            "Option_B": options[1] if len(options) > 1 else "B",
            "Option_C": options[2] if len(options) > 2 else "C",
            "Option_D": options[3] if len(options) > 3 else "D",
            "Explanation": poll_data.get("explanation", "")
        }
        yt_success = post_to_youtube_poll(yt_data)
        if yt_success:
            print("✅ YouTube Community Text Poll posted successfully!")
            return True
        else:
            print("⚠️ YouTube Community Text Poll skipped or failed.")
            return False
    except Exception as e:
        print(f"⚠️ YouTube Community integration error: {e}")
        return False

def perform_ddg_research(exam_name):
    snippets = []
    queries = [
        f"{exam_name} important concepts common mistakes tricky questions",
        f"{exam_name} syllabus tricky concepts",
        f"{exam_name} common mistakes students",
        f"{exam_name} preparation mistakes"
    ]

    print(f"[VERBOSE LOG] Researching educational concepts for '{exam_name}' via DuckDuckGo...")
    try:
        if DDGS:
            try:
                ddgs = DDGS()
                for q in queries:
                    try:
                        results = list(ddgs.text(q, max_results=4))
                        for r in results:
                            title = r.get("title", "")
                            body = r.get("body", "")
                            combined = f"{title}: {body}"
                            if not any(k in combined.lower() for k in ADMINISTRATIVE_NEWS_KEYWORDS):
                                snippets.append(combined[:300])
                    except Exception as ex:
                        print(f"⚠️ Search query '{q}' encountered issue: {ex}")
                    time.sleep(0.5)
            except Exception as ddg_err:
                print(f"⚠️ Primary DDGS research error: {ddg_err}. Using HTML search fallback...")
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
                for q in queries:
                    try:
                        res = requests.get(f"https://html.duckduckgo.com/html/?q={requests.utils.quote(q)}", headers=headers, timeout=10)
                        if res.ok:
                            from bs4 import BeautifulSoup
                            soup = BeautifulSoup(res.text, 'html.parser')
                            for a in soup.find_all('a', class_='result__url')[:3]:
                                href = a.get('href', '').strip()
                                if href:
                                    snippets.append(f"{q}: {href}")
                    except Exception:
                        pass
    except Exception as e:
        print(f"⚠️ DuckDuckGo research error: {e}")

    return snippets[:10]

def query_deepseek_selection(exam_name, research_snippets, history_data, retry_hint=""):
    # Build history summary (last 60 for broader awareness)
    history_summary = []
    banned_questions = []
    for item in history_data[-60:]:
        history_summary.append({
            "exam": item.get("exam"),
            "topic": item.get("topic"),
            "question": item.get("question")
        })
        if item.get("question"):
            banned_questions.append(item["question"])

    today_label  = datetime.now().strftime("%A, %d %B %Y")
    banned_block = "\n".join(f"  - {q}" for q in banned_questions[-30:]) if banned_questions else "  (none yet)"
    retry_block  = f"\nCRITICAL RETRY NOTE: Your previous attempt was rejected as a duplicate. {retry_hint} Generate a completely NEW question." if retry_hint else ""

    system_prompt = f"""You are the Lead Educational Content Strategist for Odisha & Central India Competitive Exams.

TODAY IS: {today_label}.
TARGET EXAM FOR TODAY: {exam_name}.{retry_block}

Your task is to generate ONE highly engaging, high-yield educational poll tailored SPECIFICALLY to the official syllabus and subject requirements of {exam_name}.

CRITICAL SYLLABUS & RELEVANCE RULES:
1. EXAM SYLLABUS ACCURACY:
   - Generate questions strictly matching official subjects for {exam_name}.
   - Even if research_snippets are sparse or from mixed sources, utilize your authoritative knowledge of competitive exams (General Studies, Reasoning, Math, English, Odia, Odisha GK, or specialized subjects) to formulate an authentic, challenging question for {exam_name}.
   - Always return status: "ACCEPT" with a fully constructed question unless a critical violation occurs.
   - For example:
     - Odisha Police SI / Constable -> Reasoning, General Studies, Odisha GK, Numerical Ability, Computer Awareness, or Law Basics.
     - OSSSC Nursing Officer -> Anatomy, Physiology, Clinical Nursing, Pharmacology, Community Health.
     - OPSC ASO / OSSC CGL -> Odia/English Grammar, General Awareness, Quantitative Aptitude, Logical Reasoning.
     - BSE Odisha OTET / OSSTET -> Child Development & Pedagogy, Odia/English Pedagogy.
2. HIGH ENGAGEMENT & HIGH YIELD:
   - Test a practical concept, confusing rule, or common trap option that aspirants frequently get wrong in real exams.
   - DO NOT generate generic motivational fluff ("study hard", "stay focused", "work hard").
   - DO NOT generate exam notifications or news updates.

POLL REQUIREMENTS:
- Exactly 3 or 4 options
- One correct answer
- At least one "common trap" option students are likely to choose
- Tests UNDERSTANDING & EXAM STRATEGY

EXPLANATION: Under 200 chars. Explain why correct = correct and trap = wrong.

BANNED QUESTIONS — DO NOT use any of these:
{banned_block}

Return ONLY valid JSON matching this schema:
{{
  "status": "ACCEPT",
  "reason": "Clear syllabus justification",
  "content_stage": "EXAM_SPECIFIC" | "EXAM_PREPARATION",
  "target_exam": "{exam_name}",
  "topic": "normalized_concept_identifier",
  "question": "Clear, engaging poll question tailored to {exam_name} syllabus?",
  "options": ["Option A", "Option B", "Option C", "Option D"],
  "correct_option_index": 0,
  "explanation": "Concise explanation under 200 chars.",
  "hook": "Short engaging hook"
}}
"""

    user_payload = {
        "today": today_label,
        "target_exam": exam_name,
        "research_snippets": research_snippets,
        "published_history": history_summary
    }

    print("[VERBOSE LOG] Invoking AI for 3-Stage Content Selection...")

    # TIER 1 (PRIMARY): Google AI Studio Gemini API
    if GEMINI_API_KEY:
        gemini_prompt = f"{system_prompt}\n\nCandidate Input:\n{json.dumps(user_payload, ensure_ascii=False)}\n\nCRITICAL: Output ONLY valid pure JSON starting with '{{' and ending with '}}'."
        for g_model in ["gemini-3.5-flash", "gemini-3.6-flash"]:
            try:
                g_url = f"https://generativelanguage.googleapis.com/v1beta/models/{g_model}:generateContent?key={GEMINI_API_KEY}"
                g_payload = {
                    "contents": [{"parts": [{"text": gemini_prompt}]}],
                    "generationConfig": {
                        "response_mime_type": "application/json",
                        "temperature": 0.7,
                        "maxOutputTokens": 2048
                    }
                }
                g_res = requests.post(g_url, headers={"Content-Type": "application/json"}, json=g_payload, timeout=20)
                if g_res.ok:
                    data = g_res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        content = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        if "</think>" in content:
                            content = content.split("</think>")[-1].strip()
                        if "```json" in content:
                            content = content.split("```json")[1].split("```")[0].strip()
                        elif "```" in content:
                            content = content.split("```")[1].split("```")[0].strip()
                        result_json = json.loads(content)
                        result_json["_ai_model"] = f"Google Gemini ({g_model}) [Primary]"
                        result_json["_ai_fallback"] = False
                        print(f"✅ [EngagementEngine] Google Gemini ({g_model}) generated poll successfully.")
                        return result_json
            except Exception as g_err:
                print(f"⚠️ [EngagementEngine] Google Gemini ({g_model}) failed: {g_err}. Falling over...")

    ai_tiers = [
        ("nvidia/nemotron-3-super-120b-a12b", "https://integrate.api.nvidia.com/v1/chat/completions", DEEPSEEK_API_KEY, 45),
        ("z-ai/glm-5.3", "https://integrate.api.nvidia.com/v1/chat/completions", DEEPSEEK_API_KEY, 45),
        ("meta/llama-3.2-11b-vision-instruct", "https://integrate.api.nvidia.com/v1/chat/completions", DEEPSEEK_API_KEY, 60)
    ]
    native_deepseek_key = (os.getenv("DEEPSEEK_API_KEY") or "").strip('"')
    if native_deepseek_key.startswith("sk-"):
        ai_tiers.append(("deepseek-chat", "https://api.deepseek.com/v1/chat/completions", native_deepseek_key, 60))

    _eng_ai_model = ai_tiers[0][0]
    _eng_ai_fallback = False

    base_payload = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)}
        ],
        "temperature": 0.8,
        "response_format": {"type": "json_object"}
    }

    for tier_idx, (m_name, endpoint, k_val, t_out) in enumerate(ai_tiers):
        clean_key = str(k_val).strip('"')
        headers = {"Authorization": f"Bearer {clean_key}", "Content-Type": "application/json"}
        req_payload = {**base_payload, "model": m_name}
        try:
            res = requests.post(endpoint, json=req_payload, headers=headers, timeout=t_out)
            if res.ok:
                data = res.json()
                content = data["choices"][0]["message"]["content"]
                if "</think>" in content:
                    content = content.split("</think>")[-1].strip()
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                
                result_json = json.loads(content)
                result_json["_ai_model"] = m_name
                result_json["_ai_fallback"] = (tier_idx > 0)
                return result_json
        except Exception as tier_err:
            print(f"⚠️ AI tier {m_name} failed: {tier_err}. Trying next tier...")
            continue

    # API failed → REJECT so the engine skips posting rather than publishing a stale static question
    return {
        "status": "REJECT",
        "reason": "AI API call failed. Skipping this run to avoid posting duplicate/stale fallback content.",
        "_ai_model": _eng_ai_model,
        "_ai_fallback": True
    }

def post_to_youtube_community_poll(poll_data):
    print("[VERBOSE LOG] Posting Engagement Text Poll to YouTube Community...")
    try:
        from post_to_youtube import post_to_youtube_poll
        options = poll_data.get("options", [])
        yt_data = {
            "Target_Exam": poll_data.get("target_exam", "Daily Quiz"),
            "Question_Text": poll_data.get("question", ""),
            "Option_A": options[0] if len(options) > 0 else "A",
            "Option_B": options[1] if len(options) > 1 else "B",
            "Option_C": options[2] if len(options) > 2 else "C",
            "Option_D": options[3] if len(options) > 3 else "D",
            "Explanation": poll_data.get("explanation", "")
        }
        yt_success = post_to_youtube_poll(yt_data)
        if yt_success:
            print("✅ YouTube Community Text Poll posted successfully!")
            return True
        else:
            print("⚠️ YouTube Community Text Poll skipped or failed.")
            return False
    except Exception as e:
        print(f"⚠️ YouTube Community integration error: {e}")
        return False

def main():
    print("==================================================")
    print("🚀 WORKFLOW 4: STRATEGIC UNLIMITED ENGAGEMENT ENGINE (ZERO-SHEET AUTONOMOUS)")
    print("==================================================\n")

    if not DEEPSEEK_API_KEY:
        msg = "ℹ️ <b>Engagement Engine Note:</b> DEEPSEEK_API_KEY is not set in GitHub secrets. Skipping poll generation gracefully."
        print("⚠️ DEEPSEEK_API_KEY is not set. Skipping engagement run gracefully.")
        send_admin_alert(msg)
        sys.exit(0)

    history_data = load_published_history()

    EXAM_ROTATION_LIST = [
        "OPSC ASO",
        "OSSC CGL",
        "OSSSC RI / AMIN",
        "Odisha Police SI",
        "BSE Odisha OTET / OSSTET",
        "OSSSC Nursing Officer",
        "Railway RRB NTPC",
        "SSC CGL",
        "IBPS PO & Clerk"
    ]

    # Select exam from EXAM_ROTATION_LIST ensuring zero recent exam repetition
    recent_posted_exams = {str(item.get("exam", "")).lower() for item in history_data[-10:]}
    available_exams = [e for e in EXAM_ROTATION_LIST if e.lower() not in recent_posted_exams]
    if not available_exams:
        available_exams = EXAM_ROTATION_LIST

    day_of_year = datetime.now().timetuple().tm_yday
    target_exam = available_exams[day_of_year % len(available_exams)]
    print(f"🎯 Target Exam for Today: '{target_exam}' (Rotated via 9-Domain Autonomous Wheel)")

    # --- TODAY-ALREADY-POSTED GUARD (Shield 1) ---
    today_str = datetime.now().strftime("%Y-%m-%d")
    posted_today = [e for e in history_data if e.get("date") == today_str]
    if posted_today:
        msg = f"✅ Engagement Engine: Poll already published today ({today_str}). Skipping to prevent duplicates."
        print(msg)
        send_admin_alert(f"ℹ️ <b>Engagement Engine:</b> Skipped — poll already posted today ({today_str}). No duplicate will be published.")
        sys.exit(0)
    # -----------------------------------------------

    # Step 1: Research
    snippets = perform_ddg_research(target_exam)

    # Step 2: DeepSeek Selection with retry loop (up to 3 attempts)
    MAX_RETRIES = 3
    poll_result = None
    retry_hint = ""
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"\n🔄 AI Attempt {attempt}/{MAX_RETRIES}...")
        result = query_deepseek_selection(target_exam, snippets, history_data, retry_hint=retry_hint)

        if result.get("status") != "ACCEPT":
            print(f"⛔ Attempt {attempt} REJECTED by AI. Reason: {result.get('reason', '')}")
            retry_hint = f"Focus strictly on core official syllabus subjects and high-yield MCQs for {target_exam}."
            if attempt == MAX_RETRIES:
                print("❌ All retries exhausted — AI rejected content generation. Skipping today.")
                send_admin_alert(f"⚠️ <b>Engagement Engine:</b> Skipped after {MAX_RETRIES} retries — AI content generation rejected for <b>{target_exam}</b>.")
                sys.exit(0)
            continue

        # --- CODE-LEVEL QUALITY & ACCURACY CHECK (Shield 1.5) ---
        is_valid_quality, qual_reason = validate_engagement_quality(result)
        if not is_valid_quality:
            retry_hint = f"Previous output rejected: {qual_reason}."
            print(f"🚫 Shield QUALITY REJECT: {qual_reason}. Retrying...")
            if attempt == MAX_RETRIES:
                print("❌ All retries exhausted — quality checks failed. Skipping today.")
                send_admin_alert(f"⚠️ <b>Engagement Engine:</b> Skipped after {MAX_RETRIES} retries — quality check failed ({qual_reason}).")
                sys.exit(0)
            continue
        # ---------------------------------------------------------

        # --- CODE-LEVEL DEDUP CHECK (Shield 2) ---
        candidate_q = result.get("question", "")
        candidate_norm = normalize_q(candidate_q)
        duplicate_entry = next(
            (e for e in history_data if normalize_q(e.get("question", "")) == candidate_norm),
            None
        )
        if duplicate_entry:
            retry_hint = f"Question '{candidate_q[:60]}' was already posted on {duplicate_entry.get('date')}."
            print(f"🚫 Shield 2 DEDUP: '{candidate_q[:60]}' already posted on {duplicate_entry.get('date')}. Retrying...")
            if attempt == MAX_RETRIES:
                print("❌ All retries exhausted — duplicate detected every time. Skipping today.")
                send_admin_alert(f"⚠️ <b>Engagement Engine:</b> Skipped after {MAX_RETRIES} retries — AI kept generating duplicate questions for <b>{target_exam}</b>.")
                sys.exit(0)
            continue  # retry with stronger hint
        # ------------------------------------------

        poll_result = result
        break  # Good unique question found

    status = poll_result.get("status") if poll_result else "REJECT"
    reason = poll_result.get("reason", "No reason provided") if poll_result else "All attempts rejected"

    if status != "ACCEPT" or not poll_result:
        print(f"⛔ Content Rejected by Quality Gate. Reason: {reason}")
        admin_msg = f"⚠️ <b>SYSTEM SKIPPED:</b> No high-value engagement content found for <b>{target_exam}</b> today.\n\n<b>Reason:</b> {reason}"
        send_admin_alert(admin_msg)
        sys.exit(0)

    content_stage = poll_result.get("content_stage", "EXAM_PREPARATION")
    question = poll_result.get("question")
    options = poll_result.get("options", [])
    correct_idx = poll_result.get("correct_option_index", 0)
    explanation = poll_result.get("explanation", "")
    topic = poll_result.get("topic", f"concept_{int(time.time())}")

    print(f"✅ Content ACCEPTED! Stage: {content_stage} | Topic: {topic}")
    print(f"❓ Question: {question}")
    print(f"📋 Options: {options}")

    # Step 3: Telegram Regular Engagement Text Poll Dispatch
    tg_success = send_telegram_regular_poll(question, options, explanation)

    # Step 4: YouTube Community Dispatch
    yt_success = post_to_youtube_community_poll(poll_result)

    if tg_success:
        today_str = datetime.now().strftime("%Y-%m-%d")
        # Record published item in history
        history_item = {
            "date": today_str,
            "exam": target_exam,
            "content_stage": content_stage,
            "topic": topic,
            "question": question,
            "options": options,
            "correct_option_index": correct_idx,
            "explanation": explanation,
            "hook": poll_result.get("hook", "")
        }
        history_data.append(history_item)
        save_published_history(history_data)

        # Send Admin Report
        ai_model_used = poll_result.get("_ai_model", "openai/gpt-oss-120b")
        ai_fallback_used = poll_result.get("_ai_fallback", False)
        ai_mode_str = f"⚠️ FALLBACK — {ai_model_used}" if ai_fallback_used else f"✅ PRIMARY — {ai_model_used}"
        admin_report = (
            f"✅ <b>Strategic Engagement Engine Published!</b>\n\n"
            f"🎯 <b>Exam:</b> {target_exam}\n"
            f"📌 <b>Stage:</b> {content_stage}\n"
            f"❓ <b>Question:</b> {question[:100]}...\n"
            f"🤖 <b>AI Model:</b> {ai_mode_str}\n\n"
            f"Telegram: ✅ | YouTube: {'✅' if yt_success else '⚠️ Skipped'}"
        )
        send_admin_alert(admin_report)
        print("🎉 Strategic Engagement Engine Execution Complete!")
    else:
        print("❌ Telegram dispatch failed.")
        send_admin_alert(f"❌ <b>Engagement Engine Failed:</b> Telegram Quiz Poll dispatch failed for {target_exam}.")

if __name__ == "__main__":
    try:
        main()
    except SystemExit as se:
        sys.exit(se.code)
    except Exception as e:
        error_msg = f"❌ <b>Strategic Engagement Engine Error</b>\n\nError details: <code>{str(e)}</code>"
        print(f"❌ Automation Error: {e}")
        try:
            send_admin_alert(error_msg)
        except Exception:
            pass
        sys.exit(1)
