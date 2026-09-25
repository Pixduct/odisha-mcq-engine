import os
import sys
import re
import json
import requests
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)

from ca_scraper import scrape_current_affairs
from shared.supabase_client import SupabaseBlogClient
from shared.pexels_image_fetcher import fetch_pexels_featured_image
from shared.ai_parser import parse_ai_json_response
from shared.telegram import send_admin_alert as send_telegram_alert

PUBLISHED_CA_HISTORY_PATH = os.path.join(SCRIPT_DIR, "published_ca_history.json")

def load_ca_history() -> List[Dict[str, Any]]:
    if os.path.exists(PUBLISHED_CA_HISTORY_PATH):
        try:
            with open(PUBLISHED_CA_HISTORY_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("items", []) if isinstance(data, dict) else data
        except Exception:
            return []
    return []

def record_ca_history(title: str, slug: str, category: str):
    history = load_ca_history()
    entry = {
        "title": title,
        "slug": slug,
        "category": category,
        "published_at": datetime.now().isoformat()
    }
    history.append(entry)
    os.makedirs(os.path.dirname(PUBLISHED_CA_HISTORY_PATH), exist_ok=True)
    with open(PUBLISHED_CA_HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump({"items": history}, f, indent=2, ensure_ascii=False)

def determine_dynamic_news_category(title: str, summary: str, source: str = "", default_category: str = "") -> str:
    """
    Delegates to 9-Category Expert AI Classifier Safeguard for Odisha and Central Exams.
    """
    from ca_formatter import classify_news_category
    return classify_news_category(title, [summary], default_category)

from ca_formatter import is_sovereign_exam_entity, HARD_POLITICAL_AND_NOISE_PATTERNS

def filter_and_curate_news(news_items: List[Dict[str, Any]], max_items: int = 8) -> List[Dict[str, Any]]:
    seen = set()
    curated = []
    
    # Priority sorting: PIB / National wire items come first
    sorted_items = sorted(
        news_items,
        key=lambda x: (
            0 if "PIB" in x.get("source", "") else
            1 if "The Hindu" in x.get("source", "") else
            2 if "Indian Express" in x.get("source", "") else 3
        )
    )

    stream_pools = {
        "odisha": [],
        "national": [],
        "economy": [],
        "science_tech": [],
        "sports": [],
        "world": []
    }

    for item in sorted_items:
        title = item.get("title", "").strip()
        summary = item.get("summary", "").strip()
        norm_title = title.lower()
        full_text_lower = f"{norm_title} {summary.lower()}"

        if not norm_title or norm_title in seen:
            continue

        has_sovereign_shield = is_sovereign_exam_entity(full_text_lower)

        # ZERO-TRUST DEFAULT-DENY GATE:
        # Every published article MUST contain a verified Sovereign Exam Entity or Syllabus Dynamic Pattern.
        if not has_sovereign_shield:
            print(f"[CAWebsitePublisher] 🚫 Zero-Trust Reject (Lacks syllabus anchor): '{title[:50]}'")
            continue

        if any(re.search(pat, full_text_lower) for pat in HARD_POLITICAL_AND_NOISE_PATTERNS):
            print(f"[CAWebsitePublisher] 🚫 Skipping non-exam noise story: '{title[:50]}'")
            continue

        seen.add(norm_title)
        
        # Categorize into stream pools
        st = item.get("stream", "national")
        if "odisha" in st or "odisha" in full_text_lower or any(d in full_text_lower for d in ['cuttack', 'bhubaneswar', 'puri', 'sambalpur', 'ganjam', 'mayurbhanj', 'rourkela']):
            stream_pools["odisha"].append(item)
        elif "economy" in st or "business" in item.get("source", "").lower() or any(w in full_text_lower for w in ['rbi', 'inflation', 'gdp', 'export', 'gst']):
            stream_pools["economy"].append(item)
        elif "science" in st or "tech" in st or any(w in full_text_lower for w in ['isro', 'satellite', 'quantum', 'ai', 'nasa', 'supercomputer']):
            stream_pools["science_tech"].append(item)
        elif "sport" in st or any(w in full_text_lower for w in ['champion', 'grand slam', 'olympic', 'world cup', 'chess', 'fide', 'gold medal']):
            stream_pools["sports"].append(item)
        elif "world" in st or item.get("priority") == "WORLD":
            stream_pools["world"].append(item)
        else:
            stream_pools["national"].append(item)

    # Balanced Multi-Stream Quorum Assembly (Guarantees every field is represented on website)
    curated = []
    # 1. Odisha Core (up to 3)
    curated.extend(stream_pools["odisha"][:3])
    # 2. National & Polity (up to 2)
    curated.extend(stream_pools["national"][:2])
    # 3. Economy & Banking (up to 2)
    curated.extend(stream_pools["economy"][:2])
    # 4. Science, Space & Tech (up to 2)
    curated.extend(stream_pools["science_tech"][:2])
    # 5. Sports & Culture (up to 1)
    curated.extend(stream_pools["sports"][:1])
    # 6. World (up to 1)
    curated.extend(stream_pools["world"][:1])

    # If below max_items, top up from remaining items across pools
    if len(curated) < max_items:
        for pool in stream_pools.values():
            for it in pool:
                if it not in curated:
                    curated.append(it)
                if len(curated) >= max_items:
                    break
            if len(curated) >= max_items:
                break

    return curated[:max_items]

def call_ai_synthesizer(news_item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    gemini_key = (
        os.getenv("GEMINI_API_KEY") or
        os.getenv("VITE_GEMINI_API_KEY") or
        ""
    ).strip('"')

    api_key = (
        os.getenv("DEEPSEEK_API_KEY") or
        os.getenv("NVIDIA_NIM_API_KEY") or
        os.getenv("OPENAI_API_KEY") or
        os.getenv("VITE_DEEPSEEK_API_KEY") or
        ""
    )
    base_url = os.getenv("VITE_DEEPSEEK_BASE_URL") or os.getenv("DEEPSEEK_BASE_URL", "https://integrate.api.nvidia.com/v1")
    url = f"{base_url.rstrip('/')}/chat/completions"

    today_iso       = datetime.now().strftime("%Y-%m-%d")
    yesterday_iso   = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    today_label     = datetime.now().strftime("%A, %d %B %Y")

    if not gemini_key and not api_key:
        print("[CAWebsitePublisher] ❌ Neither GEMINI_API_KEY nor DEEPSEEK_API_KEY is set — AI cannot run.")
        return None

    print(f"[CAWebsitePublisher] ✅ AI Engine Active | Gemini: {'SET' if gemini_key else 'NONE'} | NVIDIA: {'SET' if api_key else 'NONE'} | Today: {today_iso}")

    clean_api_key = api_key.replace('"', '').replace("'", "").strip()

    headers = {
        "Authorization": f"Bearer {clean_api_key}",
        "Content-Type": "application/json"
    }

    model = "nvidia/nemotron-3-super-120b-a12b" if "nvidia.com" in base_url else "deepseek-chat"

    raw_title = news_item.get("title", "")
    raw_summary = news_item.get("summary", "")
    raw_source = news_item.get("source", "PIB / News")
    raw_priority = news_item.get("priority", "")

    system_prompt = (
        f"You are the Lead Senior Current Affairs Analyst & Exam Syllabus Architect for OPSC, OSSC, OSSSC, SSC CGL, Railway RRB, and Banking Exams.\n"
        f"TODAY IS: {today_label}.\n"
        f"CRITICAL DATE-MATCH RULE: ONLY process and publish news whose event or publication date is verified as TODAY ({today_iso}) or YESTERDAY ({yesterday_iso}). If there is any issue verifying that a news item is from today, SKIP THAT NEWS ITEM IMMEDIATELY. Only 100% verified fresh news from today will be published.\n"
        f"Set event_date to {today_iso} for all articles you generate.\n\n"
        "CRITICAL TRUTHFULNESS, THE 3-TIER EXAM BENCHMARK & DYNAMIC 5W1H RULES:\n"
        "1. THE COMPREHENSIVE 8-DOMAIN EXAM BENCHMARK (MILESTONES VS DRAMA):\n"
        "   - Act as a Senior Paper Setter for OPSC, UPSC, SSC, and Banking exams. Publish verified milestones across all 8 domains: 1. Odisha State Affairs (Cabinet approvals, 30 districts, Subhadra/KALIA schemes, OPSC recruitment), 2. National Polity & Law, 3. Economy & Banking (RBI, GST, export records, UPI global), 4. Science, Space & Tech (ISRO, DRDO, Quantum, AI supercomputing), 5. Sports Milestones (Grand Slams, Chess Championships, Olympics, World Cups, Khel Ratna), 6. Art, Culture & GI Tags (UNESCO, Sahitya Akademi, Jnanpith, ASI excavations), 7. Environment & Ecology (Ramsar, Tiger Reserves, COP pacts), 8. International Relations & Global GK (G20, BRICS, SCO, UN, Global Indices).\n"
        "   - STRICT BAN ON POLITICAL SPEECHES & AGITATIONS: NEVER generate articles for political party dharnas, protests outside police stations, gherao, sloganeering, political speeches criticizing past governments, party worker rallies, or village mob clashes! Only actual statutory Acts, Cabinet approvals, Gazette policies, tournament championships, scientific discoveries, and treaties are accepted.\n"
        "   - Always check the article dateline/header (e.g. 'DHARWAD:', 'NELLORE:', 'BHUBANESWAR:', 'GENEVA:') for event location details, even if the city/district is not repeated in the body text!\n"
        "   - BAN ON ISOLATED DIRECTIONAL WORDS: NEVER write isolated directional fragments like 'in North', 'in South', 'in East', 'in West' without naming the specific Country, State, River, Lake, or Sea! (e.g. NEVER say 'Boat capsizes in North' — specify 'Niger River (Kebbi State, Nigeria)' or 'Brahmaputra River (Assam, India)').\n"
        "   - NATIONAL SCOPE: Whenever an Indian district or city is mentioned, ALWAYS state its parent State (e.g., 'Nellore District (Andhra Pradesh)', 'Dharwad District (Karnataka)', 'Indore (Madhya Pradesh)', 'Wayanad (Kerala)'). NEVER leave an Indian district without its State!\n"
        "   - ODISHA SCOPE: Specify District & Block/Tehsil (e.g., 'Ganjam District, Chhatrapur Block' or 'Dhenkanal District'). Do NOT add redundant 'Odisha, India'.\n"
        "   - GLOBAL SCOPE: Whenever a world city or region is mentioned, ALWAYS state its Country (e.g., 'Bavaria (Germany)', 'Geneva (Switzerland)'). If a story only has vague directions without naming the country/state, REJECT IT!\n"
        "   - ZERO GHOST ACTORS: Never use vague ghost actors like 'the government', 'officials', or 'recent reports'. Always state the concrete Authority, Ministry, Board, Bank, or Court!\n"
        "   - CONCRETE SCHEMES & SPECIFICS: Never say 'a scheme' or 'an initiative'. State the official Scheme/Yojana Name, specific affected student/farmer/trade group, and budget figures.\n"
        "   - Naturally include 5W1H details (Where, Who, When, Numbers, Why) if present in the story or dateline.\n"
        "   - Ignore ONLY non-news corporate publisher footers (e.g. 'Copyright 2026 The Hindu Group, Chennai'). NEVER ignore genuine article datelines!\n"
        "   - Do NOT force bracketed placeholders like [District Name] or make up fake names if details are missing.\n"
        "   - If optional elements like `data_table_html` or `static_gk_pointers` have no relevant data in the raw news, pass an empty string `\"\"` or a concise 2-row table containing only available metrics. Do NOT generate empty template tables with fake or missing values.\n"
        "2. DYNAMIC REAL-WORLD NEWS HANDLING (NO FIXED SCHEMAS OR TOPIC CONSTRAINTS):\n"
        "   - Real-world news is infinitely varied (disaster relief, space launches, economic indicators, judicial verdicts, sports awards, policy notices, multilateral treaties).\n"
        "   - Adapt the HTML headings, callout boxes, and executive summary dynamically to match whatever topic is actually being reported.\n"
        "3. ALL OUTPUT MUST BE IN SIMPLE, EASY-TO-UNDERSTAND ENGLISH (BEGINNER-FRIENDLY):\n"
        "   - Use clear, everyday English so every beginner student understands immediately without needing a dictionary.\n"
        "   - HEADLINE ACRONYM REASONING: Freely use standard, syllabus-studied exam bodies (e.g. ISRO, DRDO, RBI, SEBI, NABARD, NITI Aayog, UPSC, OPSC, IMF, NATO, ASEAN, NCERT, ICAR, AIIMS, CSIR, BARC, GST, SC, HC, WHO, UN). NEVER use obscure local community unions or niche regional acronyms (like KPMS, KSU, DKS) in headlines! Either write out their descriptive name in plain English or skip local campus disputes.\n"
        "   - Avoid heavy academic jargon or difficult words. Use simple words: 'banned' (not 'proscribed'), 'started/launched' (not 'inaugurated'), 'passed/issued' (not 'promulgated'), 'protect/save' (not 'mitigate degradation'), 'approved funds' (not 'sanctioned budgetary allocation').\n"
        "   - If the raw news title, summary, or text is in Hindi, Odia, or any regional language (e.g., 'राजस्थान दौरे में...', 'ସୁଭଦ୍ରା ଯୋଜନା...'), IMMEDIATELY TRANSLATE IT TO CLEAR, SIMPLE ENGLISH before generating the article.\n"
        "   - FOR ODISHA STATE NEWS: Focus on Cabinet decisions, OPSC/OSSC syllabus mapping, district impact, and Odisha cultural/historical context. Include an amber callout box `<div class=\"p-4 rounded-2xl bg-amber-50 border border-amber-200 text-amber-900 font-medium my-4\">`.\n"
        "   - FOR GOVT SCHEMES & POLICIES: Focus on Nodal Ministry, Target Beneficiaries, Budgetary Outlay, Implementation Timeline, and Key Provisions. Include an emerald callout box `<div class=\"p-4 rounded-2xl bg-emerald-50 border border-emerald-200 text-emerald-900 font-medium my-4\">`.\n"
        "   - FOR DEFENSE / SCIENCE & TECH: Focus on Technical Specs, DRDO/ISRO details, Operational Range, Environmental Acts, or Payload Metrics. Include an indigo callout box `<div class=\"p-4 rounded-2xl bg-indigo-50 border border-indigo-200 text-indigo-900 font-medium my-4\">`.\n"
        "   - FOR INTERNATIONAL RELATIONS: Focus on Treaties, Headquarters, Bilateral Trade, Multilateral Forums (UN, G20, BRICS), and Geopolitical Significance. Include a purple callout box `<div class=\"p-4 rounded-2xl bg-purple-50 border border-purple-200 text-purple-900 font-medium my-4\">`.\n"
        "   - FOR APPOINTMENTS & AWARDS: Focus on Role/Organization background, key contributions, past predecessors/recipients, and Static GK quick facts.\n"
        "4. FORMATTING REQUIREMENTS IN `full_context`:\n"
        "   - Use clear HTML subheadings (`<h3 class=\"text-lg font-extrabold text-slate-900 mt-6 mb-2 flex items-center gap-2\">Section Title</h3>`).\n"
        "   - Break long paragraphs into short, comfortable 2-3 sentence paragraphs.\n"
        "   - Use formatted unordered lists (`<ul class=\"list-disc pl-5 space-y-1.5 my-3\"><li>...</li></ul>`) for key provisions.\n"
        "   - Embed high-yield static GK links and constitutional articles where applicable.\n"
        "5. HIGH-YIELD EXAM MCQS REQUIREMENT (TARGET: UP TO 5 IMPORTANT MCQS PER TOPIC):\n"
        "   - Generate UP TO 5 HIGHLY IMPORTANT, exam-aligned MCQs in `mcqs` array. Focus on core syllabus concepts, constitutional articles, nodal ministries, static GK background, and analytical impacts.\n"
        "   - DO NOT generate shallow, trivial, or generic questions. If a topic has rich exam potential, generate 5 strong MCQs. If the content has less depth, generate as many strong MCQs as naturally fit (e.g. 3 or 4). It is NOT mandatory to force 5 questions if the content does not support it.\n"
        "   - Each MCQ object must have `question`, `options` [A, B, C, D], `correct_answer` ('A', 'B', 'C', or 'D'), and detailed `explanation`.\n\n"
        "Return ONLY valid JSON matching this schema:\n"
        "{\n"
        '  "title": "...",\n'
        '  "slug": "...",\n'
        '  "category": "Odisha State News",\n'
        '  "event_date": "' + today_iso + '",\n'
        '  "summary": "• Point 1\\n• Point 2\\n• Point 3",\n'
        '  "full_context": "<h3 class=\\"text-lg font-extrabold text-slate-900 mt-6 mb-2\\">📌 Key Provisions</h3><p>Detailed analysis...</p>",\n'
        '  "static_gk_pointers": "<div class=\\"bg-slate-50 dark:bg-[#0B1528] p-4 rounded-2xl border border-slate-200 dark:border-slate-800 my-4\\"><h4 class=\\"font-extrabold text-slate-900 dark:text-blue-400 text-sm mb-2\\">💡 OPSC & SSC Static GK Pointers</h4><ul class=\\"list-disc pl-5 text-xs text-slate-700 dark:text-slate-300 space-y-1\\"><li>Point 1</li></ul></div>",\n'
        '  "data_table_html": "<div class=\\"overflow-x-auto my-4\\"><table class=\\"w-full text-xs text-left border border-slate-200 dark:border-slate-800 rounded-xl\\"><thead><tr class=\\"bg-slate-100 dark:bg-[#0B1528]\\"><th class=\\"p-2.5 font-bold text-slate-700 dark:text-slate-300\\">Metric</th><th class=\\"p-2.5 font-bold text-slate-700 dark:text-slate-300\\">Details</th></tr></thead><tbody><tr class=\\"bg-white dark:bg-[#060B16]\\"><td class=\\"p-2.5 border-t border-slate-200 dark:border-slate-800 text-slate-800 dark:text-slate-200\\">Nodal Agency</td><td class=\\"p-2.5 border-t border-slate-200 dark:border-slate-800 text-slate-800 dark:text-slate-200\\">Details</td></tr></tbody></table></div>",\n'
        '  "mcqs": [\n'
        '    {"question": "Q1 text...", "options": ["A) ...", "B) ...", "C) ...", "D) ..."], "correct_answer": "A", "explanation": "Detailed explanation..."},\n'
        '    {"question": "Q2 text...", "options": ["A) ...", "B) ...", "C) ...", "D) ..."], "correct_answer": "B", "explanation": "Detailed explanation..."},\n'
        '    {"question": "Q3 text...", "options": ["A) ...", "B) ...", "C) ...", "D) ..."], "correct_answer": "C", "explanation": "Detailed explanation..."}\n'
        '  ],\n'
        '  "sources": "PIB Odisha"\n'
        "}"
    )

    user_prompt = f"Raw News Item:\nTitle: {raw_title}\nSummary: {raw_summary}\nSource: {raw_source}\nPriority: {raw_priority}"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.3,
        "response_format": {"type": "json_object"}
    }

    ai_tiers = [
        {
            "name": "NVIDIA Nemotron 3 Super 120B",
            "model": "nvidia/nemotron-3-super-120b-a12b",
            "key": clean_api_key,
            "url": "https://integrate.api.nvidia.com/v1/chat/completions",
            "timeout": 45
        },
        {
            "name": "NVIDIA GLM 5.3",
            "model": "z-ai/glm-5.3",
            "key": clean_api_key,
            "url": "https://integrate.api.nvidia.com/v1/chat/completions",
            "timeout": 45
        },
        {
            "name": "NVIDIA Llama 3.2 11B Vision Instruct",
            "model": "meta/llama-3.2-11b-vision-instruct",
            "key": clean_api_key,
            "url": "https://integrate.api.nvidia.com/v1/chat/completions",
            "timeout": 60
        }
    ]

    try:
        content = ""
        ai_success = False

        # TIER 1 (PRIMARY): Google AI Studio Gemini API (Smart Free Tier)
        # Gemini is always tried FIRST with retry-with-backoff on 429 (quota) and 503 (demand).
        gemini_last_err = ""
        GEMINI_MODELS = ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.6-flash", "gemini-3.7-flash", "gemini-3.8-flash", "gemini-3.1-flash-lite"]
        if gemini_key:
            gemini_prompt = f"{system_prompt.strip()}\n\n{user_prompt.strip()}"
            for g_model in GEMINI_MODELS:
                if ai_success:
                    break
                max_model_attempts = 2
                for attempt in range(1, max_model_attempts + 1):
                    try:
                        print(f"[CAWebsitePublisher] 🚀 [Primary AI] Calling Google Gemini ({g_model}) attempt {attempt}...")
                        g_url = f"https://generativelanguage.googleapis.com/v1beta/models/{g_model}:generateContent?key={gemini_key}"
                        g_payload = {
                            "contents": [{"parts": [{"text": gemini_prompt}]}],
                            "generationConfig": {
                                "response_mime_type": "application/json",
                                "temperature": 0.2,
                                "maxOutputTokens": 3000
                            }
                        }
                        g_res = requests.post(g_url, headers={"Content-Type": "application/json"}, json=g_payload, timeout=35)
                        if g_res.ok:
                            g_json = g_res.json()
                            candidates = g_json.get("candidates", [])
                            if candidates:
                                raw_t = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                                if raw_t and raw_t.strip():
                                    content = raw_t
                                    ai_success = True
                                    print(f"[CAWebsitePublisher] ✅ [Google Gemini - {g_model}] Responded successfully.")
                                    break
                        elif g_res.status_code == 429:
                            gemini_last_err = f"{g_model}: HTTP 429 quota"
                            if attempt < max_model_attempts:
                                import time as _t
                                print(f"[CAWebsitePublisher] ⏳ [Google Gemini - {g_model}] HTTP 429 quota — waiting 65s for quota reset...")
                                _t.sleep(65)
                                continue
                            else:
                                print(f"[CAWebsitePublisher] ⚠️ [Google Gemini - {g_model}] Quota exhausted after retry. Trying next model...")
                        elif g_res.status_code == 503:
                            gemini_last_err = f"{g_model}: HTTP 503 high demand"
                            if attempt < max_model_attempts:
                                import time as _t
                                print(f"[CAWebsitePublisher] ⏳ [Google Gemini - {g_model}] HTTP 503 high demand — waiting 30s then retrying...")
                                _t.sleep(30)
                                continue
                            else:
                                print(f"[CAWebsitePublisher] ⚠️ [Google Gemini - {g_model}] Still busy after retry. Trying next model...")
                        else:
                            gemini_last_err = f"{g_model}: HTTP {g_res.status_code} - {g_res.text[:100]}"
                            print(f"[CAWebsitePublisher] ⚠️ [Google Gemini - {g_model}] HTTP {g_res.status_code}. Trying next model...")
                        break
                    except Exception as g_err:
                        gemini_last_err = f"{g_model}: {g_err}"
                        print(f"[CAWebsitePublisher] ⚠️ [Google Gemini - {g_model}] Error: {g_err}. Trying next model...")
                        break

            if ai_success:
                print(f"[CAWebsitePublisher] ✅ Gemini Primary AI succeeded! NVIDIA NIM fallback NOT needed.")
            else:
                print(f"[CAWebsitePublisher] ⚠️ All Gemini models exhausted. Transitioning to NVIDIA NIM as last resort...")

        # TIER 2+ (FALLBACK): High-Throughput NVIDIA NIM Models
        if not ai_success and clean_api_key:
            for tier_idx, tier in enumerate(ai_tiers):
                tier_name = tier["name"]
                model_name = tier["model"]
                key_val = str(tier["key"]).strip('"')
                call_url = tier["url"]
                timeout_val = tier["timeout"]

                call_headers = {"Authorization": f"Bearer {key_val}", "Content-Type": "application/json"}
                call_payload = {**payload, "model": model_name}

                for attempt in range(1, 3):
                    try:
                        res = requests.post(call_url, headers=call_headers, json=call_payload, timeout=timeout_val)
                        if res.ok:
                            raw_c = res.json().get('choices', [{}])[0].get('message', {}).get('content', '')
                            if raw_c and raw_c.strip():
                                content = raw_c
                                ai_success = True
                                print(f"[CAWebsitePublisher] ✅ [{tier_name}] Responded successfully on attempt {attempt}.")
                                try:
                                    from shared.telegram import send_ai_fallback_notification
                                    send_ai_fallback_notification(
                                        engine="ca_website_publisher (Website Article Generator)",
                                        primary_error=gemini_last_err or "Gemini models exhausted",
                                        fallback_model=f"{tier_name} ({model_name})",
                                        context_topic=raw_title
                                    )
                                except Exception as alert_err:
                                    print(f"⚠️ [Alert Failed]: {alert_err}")
                                break
                        else:
                            print(f"[CAWebsitePublisher] ⚠️ [{tier_name}] HTTP {res.status_code} on attempt {attempt}")
                    except Exception as tier_err:
                        print(f"[CAWebsitePublisher] ⚠️ [{tier_name}] Attempt {attempt} failed ({tier_err}). Retrying/Failing over...")
                    time.sleep(1.5)

                if ai_success:
                    break

        if not ai_success or not content:
            raise RuntimeError("All AI Primary (Gemini) & Fallback (NVIDIA NIM) Tiers exhausted in ca_website_publisher.")

        parsed = parse_ai_json_response(content)
        if isinstance(parsed, dict) and parsed.get("title"):
                title = str(parsed.get("title", "")).strip()
                summary = str(parsed.get("summary", "")).strip()
                full_context = str(parsed.get("full_context", "")).strip()

                # PLACEHOLDER REJECTION & SANITIZATION GATE:
                # Reject any generated article containing unreplaced template placeholders like [District Name], [River Name], [Block/Taluk]
                import re
                from ca_formatter import HARD_POLITICAL_AND_NOISE_PATTERNS
                placeholder_pattern = r'\[(district|river|block|taluk|ministry|state|agency|department|date|number|name|insert|amount|location)[^\]]*\]'
                combined_text = f"{title} {summary} {full_context}".lower()

                if re.search(placeholder_pattern, combined_text):
                    print(f"[CAWebsitePublisher] 🚫 QUALITY REJECT: Contains unreplaced template placeholders (e.g. [District Name] / [River Name])")
                    return None

                if any(re.search(pat, combined_text) for pat in HARD_POLITICAL_AND_NOISE_PATTERNS):
                    print(f"[CAWebsitePublisher] 🚫 QUALITY REJECT: Matched 15-category non-exam noise blacklist: '{title[:50]}'")
                    return None

                if len(title) < 10 or "government announces" in title.lower() or "important update" in title.lower():
                    print(f"[CAWebsitePublisher] 🚫 QUALITY REJECT: Generic or bad title: '{title[:50]}'")
                    return None

                if not summary or not full_context or len(full_context) < 100:
                    print(f"[CAWebsitePublisher] 🚫 QUALITY REJECT: Summary or full context missing/too short")
                    return None

                parsed["event_date"] = today_iso
                parsed["category"] = determine_dynamic_news_category(
                    title,
                    summary,
                    raw_source,
                    parsed.get("category", raw_priority)
                )
                return parsed
    except Exception as e:
        print(f"[CAWebsitePublisher] AI generation error: {e}")

    return None

def publish_daily_ca_website():
    print("[CAWebsitePublisher] Running UNRESTRICTED Daily Current Affairs Website Publisher...")

    history = load_ca_history()
    seen_titles = {h.get("title", "").lower() for h in history if h.get("title")}

    client = SupabaseBlogClient()
    try:
        existing_db_items = client.fetch_all_current_affairs()
        for item in existing_db_items:
            t = (item.get("title") or item.get("name") or "").strip().lower()
            if t:
                seen_titles.add(t)
    except Exception as db_err:
        print(f"[CAWebsitePublisher] Note: DB pre-fetch notice: {db_err}")

    try:
        raw_items, _ = scrape_current_affairs()
    except Exception as ex:
        print(f"[CAWebsitePublisher] Error fetching news items: {ex}")
        raw_items = []

    print(f"[CAWebsitePublisher] Scraped {len(raw_items)} raw news items.")

    new_items = [item for item in raw_items if item.get("title", "").strip().lower() not in seen_titles]
    print(f"[CAWebsitePublisher] Found {len(new_items)} fresh news items.")

    if not new_items:
        print("[CAWebsitePublisher] No fresh news items to publish.")
        report_msg = (
            f"🌐 <b>Daily CA Website Publisher Execution Report</b>\n\n"
            f"📅 <b>Date:</b> {datetime.now().strftime('%d %B %Y')}\n"
            f"🔍 <b>Scraped Raw Items:</b> {len(raw_items)}\n"
            f"🎯 <b>Fresh Unpublished Candidates:</b> 0\n"
            f"🚀 <b>New Articles Published to DB:</b> 0\n"
            f"ℹ️ <b>Status Note:</b> All top daily stories are already published on Website DB ✅\n"
            f"🤖 <b>AI Engine Status:</b> Active ✅"
        )
        send_telegram_alert("CA_WEBSITE_PUBLISHER", "INFO", {"message": report_msg})
        return

    curated_items = filter_and_curate_news(new_items, max_items=6)
    print(f"[CAWebsitePublisher] Curated {len(curated_items)} high-yield exam articles out of {len(new_items)} raw candidates.")

    published_count = 0
    start_time = time.time()
    MAX_RUN_TIME_SECONDS = 600

    for news_item in curated_items:
        if (time.time() - start_time) > MAX_RUN_TIME_SECONDS:
            print(f"[CAWebsitePublisher] ⏳ Reached 10-minute execution threshold. Stopping run cleanly.")
            break

        raw_t = news_item.get("title", "").strip().lower()
        if raw_t in seen_titles:
            continue

        digest = call_ai_synthesizer(news_item)
        if not digest:
            continue

        title = digest.get("title", "").strip()
        slug = digest.get("slug", "").strip()
        category = digest.get("category", "General Current Affairs")

        if not slug:
            slug = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
        pexels_res = fetch_pexels_featured_image(
            search_query=title,
            article_slug=slug,
            title=title,
            category=category,
            target_exam="Current Affairs"
        )
        if isinstance(pexels_res, dict):
            img_url = pexels_res.get("image_url") or "https://images.pexels.com/photos/3184325/pexels-photo-3184325.jpeg?auto=compress&cs=tinysrgb&w=1200"
        elif isinstance(pexels_res, str) and pexels_res.startswith("http"):
            img_url = pexels_res
        else:
            img_url = "https://images.pexels.com/photos/3184325/pexels-photo-3184325.jpeg?auto=compress&cs=tinysrgb&w=1200"

        digest["image_url"] = img_url
        digest["featured_image"] = img_url

        try:
            res = client.insert_current_affairs(digest)
            if res:
                published_count += 1
                seen_titles.add(raw_t)
                record_ca_history(title, slug, category)
                print(f"[CAWebsitePublisher] ✅ Published Current Affairs article: '{title}' [{category}]")
        except Exception as insert_err:
            print(f"[CAWebsitePublisher] ❌ Error inserting article '{title}': {insert_err}")

    status_note = f"Published <b>{published_count}</b> new article(s) to Website DB ✅" if published_count > 0 else f"All top stories for today are already published on Website DB ℹ️"
    report_msg = (
        f"🌐 <b>Daily CA Website Publisher Execution Report</b>\n\n"
        f"📅 <b>Date:</b> {datetime.now().strftime('%d %B %Y')}\n"
        f"🔍 <b>Scraped Raw Items:</b> {len(raw_items)}\n"
        f"🎯 <b>Fresh Unpublished Candidates:</b> {len(new_items)}\n"
        f"🚀 <b>New Articles Published to DB:</b> {published_count}\n"
        f"ℹ️ <b>Status Note:</b> {status_note}\n"
        f"🤖 <b>AI Engine Status:</b> Active ✅"
    )
    send_telegram_alert("CA_WEBSITE_PUBLISHER", "SUCCESS" if published_count > 0 else "INFO", {"message": report_msg})
    print(f"[CAWebsitePublisher] Completed. Published {published_count} website articles.")

if __name__ == "__main__":
    try:
        publish_daily_ca_website()
    except SystemExit as se:
        sys.exit(se.code)
    except Exception as e:
        print(f"[CAWebsitePublisher] ❌ Fatal Error: {e}")
        try:
            send_telegram_alert("CA_WEBSITE_PUBLISHER", "FAILED", {"error": str(e)})
        except Exception:
            pass
        sys.exit(1)
