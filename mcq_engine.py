import os
import sys
import json
import base64
import time
import re
import requests
try:
    import gspread
    from google.oauth2.service_account import Credentials
except ImportError:
    gspread = None
    Credentials = None
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "")
MCQ_BATCH_SIZE = int(os.getenv("MCQ_BATCH_SIZE", "1"))

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
).strip('"')
DEEPSEEK_BASE_URL = (
    os.getenv("DEEPSEEK_BASE_URL") or
    os.getenv("VITE_DEEPSEEK_BASE_URL") or
    "https://integrate.api.nvidia.com/v1"
).strip('"')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CREDS_FILE = os.path.join(SCRIPT_DIR, "google_credentials.json")
HISTORY_FILE = os.path.join(SCRIPT_DIR, "published_history.json")
TEMPLATE_FILE = os.path.join(SCRIPT_DIR, "templates", "template_mcq.html")
TEMP_HTML_FILE = os.path.join(SCRIPT_DIR, "temp.html")
OUTPUT_IMAGE_FILE = os.path.join(SCRIPT_DIR, "output_mcq.png")
STATE_FILE = os.path.join(SCRIPT_DIR, "yt_state.json")
PROFILE_DIR = os.path.join(SCRIPT_DIR, "yt_profile")

def send_telegram_notification(bot_token, chat_id, message, image_path=None):
    try:
        print(f"[VERBOSE LOG] Sending Telegram message to Chat ID: {chat_id}...")
        if image_path and os.path.exists(image_path):
            url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            with open(image_path, "rb") as photo_file:
                payload = {"chat_id": chat_id, "caption": message, "parse_mode": "HTML", "disable_notification": False}
                files = {"photo": photo_file}
                res = requests.post(url, data=payload, files=files, timeout=25)
                if not res.ok:
                    print(f"❌ Telegram API Error ({res.status_code}): {res.text}")
                return res.json()
        else:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML", "disable_notification": False, "disable_web_page_preview": False}
            res = requests.post(url, data=payload, timeout=20)
            if not res.ok:
                plain_text = re.sub(r'<[^>]+>', '', message)
                res = requests.post(url, data={"chat_id": chat_id, "text": plain_text}, timeout=20)
            return res.json() if res.ok else None
    except Exception as e:
        print(f"❌ Failed to send Telegram notification: {e}")
        return None

def send_telegram_quiz_poll(bot_token, chat_id, question, options, correct_option_id, explanation=""):
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendPoll"
        print(f"[VERBOSE LOG] Sending Native Telegram Quiz Poll to Public Channel ({chat_id})...")
        
        # Clean and clamp options (Telegram requires 2-10 options, each 1-100 characters)
        clean_options = []
        for opt in options:
            opt_str = str(opt).strip()
            if not opt_str:
                continue
            if len(opt_str) > 100:
                print(f"⚠️ Truncating Option exceeding 100 chars ({len(opt_str)} chars): {opt_str[:40]}...")
                opt_str = opt_str[:97].rstrip() + "..."
            clean_options.append(opt_str)

        if len(clean_options) < 2:
            print(f"❌ Telegram sendPoll Error: Less than 2 valid options provided ({len(clean_options)}).")
            return False

        if correct_option_id < 0 or correct_option_id >= len(clean_options):
            correct_option_id = 0

        raw_payload = {
            "chat_id": chat_id,
            "question": question[:300],
            "options": json.dumps(clean_options),
            "is_anonymous": True,
            "type": "quiz",
            "correct_option_id": correct_option_id
        }
        if explanation:
            # Telegram explanation limit: max 200 chars, max 2 line breaks
            clean_expl = re.sub(r'<[^>]+>', '', explanation).strip()
            clean_expl = re.sub(r'[\r\n\t]+', ' ', clean_expl).strip()
            if len(clean_expl) > 160:
                clean_expl = clean_expl[:157].rstrip() + "..."
            formatted_expl = f"{clean_expl}\n🌐 odishaexamprep.in"
            raw_payload["explanation"] = formatted_expl[:200]

        res = requests.post(url, data=raw_payload, timeout=20)
        if res.ok:
            print("✅ Native Telegram Quiz Poll posted successfully!")
            return True
        else:
            print(f"❌ Telegram sendPoll Error ({res.status_code}): {res.text}")
            return False
    except Exception as e:
        print(f"❌ Failed to send Telegram Quiz Poll: {e}")
        return False

def retry_google_api(func, max_retries=5, initial_delay=3, backoff_factor=2, action_name="Google API operation"):
    delay = initial_delay
    last_exception = None
    for attempt in range(1, max_retries + 1):
        try:
            return func()
        except Exception as e:
            last_exception = e
            err_str = str(e)
            print(f"⚠️ [Attempt {attempt}/{max_retries}] {action_name} failed: {err_str}")
            if attempt < max_retries:
                print(f"⏳ Retrying {action_name} in {delay}s (exponential backoff)...")
                time.sleep(delay)
                delay *= backoff_factor
            else:
                print(f"❌ All {max_retries} attempts failed for {action_name}.")
                raise last_exception

def fetch_pending_questions(limit=1):
    print(f"[VERBOSE LOG] Fetching pending questions from Google Sheets (Limit: {limit})...")
    if not gspread or not Credentials:
        raise ImportError("gspread or google-auth not installed.")
    
    creds_json_str = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if creds_json_str:
        print("[VERBOSE LOG] Parsing GOOGLE_CREDENTIALS_JSON from environment variable...")
        try:
            creds_info = json.loads(creds_json_str)
        except Exception:
            try:
                decoded = base64.b64decode(creds_json_str).decode('utf-8')
                creds_info = json.loads(decoded)
            except Exception as e:
                raise ValueError(f"Failed to parse GOOGLE_CREDENTIALS_JSON: {e}")
        creds = Credentials.from_service_account_info(creds_info, scopes=SCOPES)
    elif os.path.exists(CREDS_FILE):
        print(f"[VERBOSE LOG] Loading service account from {CREDS_FILE}...")
        creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
    else:
        raise FileNotFoundError("Google Credentials file or GOOGLE_CREDENTIALS_JSON environment variable not found.")

    def _load_sheet_records():
        client = gspread.authorize(creds)
        possible_sheet_names = [
            "Odisha_MCQ_Engine",
            "Odisha_MCQ_Engine.xlsx",
            "Odisha_MCQ_Engine .xlsx",
            "Odisha_MCQ_Engine ",
            "Odisha_Editorial_Queue",
            "Odisha_Editorial_Queue.xlsx",
            "Odisha_Editorial_Queue .xlsx",
            "OdishaExamPrep_Queue"
        ]
        spreadsheet = None
        for s_name in possible_sheet_names:
            try:
                spreadsheet = client.open(s_name)
                print(f"[VERBOSE LOG] Connected to Google Sheet: '{s_name}'")
                break
            except Exception:
                continue

        if not spreadsheet:
            try:
                all_sheets = client.openall()
                for s in all_sheets:
                    title_low = s.title.lower()
                    if "mcq" in title_low or "editorial" in title_low or "queue" in title_low:
                        spreadsheet = s
                        print(f"[VERBOSE LOG] Auto-discovered Spreadsheet: '{s.title}'")
                        break
            except Exception as e:
                print(f"[VERBOSE LOG] Auto-discovery note: {e}")

        if not spreadsheet:
            raise FileNotFoundError(f"Could not find any matching Google Sheet: {possible_sheet_names}")

        # Tab resolution
        sheet = None
        ws_map = {ws.title.lower().strip(): ws for ws in spreadsheet.worksheets()}
        for candidate_tab in ["mcq", "mcqs", "questions", "daily_mcq", "quiz", "sheet1"]:
            if candidate_tab in ws_map:
                sheet = ws_map[candidate_tab]
                break
        if not sheet:
            sheet = spreadsheet.sheet1

        print(f"[VERBOSE LOG] Reading records from worksheet '{sheet.title}'...")
        records = sheet.get_all_records()
        return sheet, records

    sheet, records = retry_google_api(_load_sheet_records, max_retries=5, initial_delay=3, action_name="Fetch Google Sheet Records")
    print(f"Total rows found in sheet: {len(records)}")

    # Detect Status column index dynamically
    raw_headers = sheet.row_values(1)
    status_col_idx = 10
    for idx, h in enumerate(raw_headers, start=1):
        if "status" in h.lower():
            status_col_idx = idx
            break

    pending_items = []
    for row_index, row in enumerate(records, start=2):
        status = str(row.get('Status') or row.get('status', '')).strip().lower()
        if status in ['pending', 'todo', 'queued', '']:
            pending_items.append((row_index, row))
            if len(pending_items) >= limit:
                break

    print(f"✅ Found {len(pending_items)} pending questions for this run (Limit: {limit}). Status col: {status_col_idx}")
    return sheet, pending_items, status_col_idx

def normalize_and_heal_mcq(row):
    """
    Cleans and repairs question data:
    1. Detects truncated question stems where Option A contains the remainder of the sentence.
    2. Strips extra whitespace.
    3. Normalizes correct_option index.
    4. Enforces Telegram & Display length boundaries.
    """
    healed = dict(row)
    target_exam = str(healed.get("Target_Exam", "")).strip()
    question_text = str(healed.get("Question_Text", "")).strip()
    
    opt_a = str(healed.get("Option_A", "")).strip()
    opt_b = str(healed.get("Option_B", "")).strip()
    opt_c = str(healed.get("Option_C", "")).strip()
    opt_d = str(healed.get("Option_D", "")).strip()
    
    correct_raw = str(healed.get("Correct_Option", "A")).strip().upper()
    mapping = {"A": 0, "B": 1, "C": 2, "D": 3, "1": 0, "2": 1, "3": 2, "4": 3}
    correct_idx = mapping.get(correct_raw, 0)
    
    stem_indicators = [
        "is defined as", "is known as", "refers to", "characterized by", "means that",
        "which of the following", "ending with the", "beginning with", "period of"
    ]
    should_merge = False
    if opt_a:
        is_short_stem = len(question_text.split()) <= 6 or len(question_text) < 35
        ends_with_colon = opt_a.endswith(":")
        ends_with_open = question_text.lower().rstrip().endswith((",", "in", "the", "for", "with", "during", "at", "by", "of", "to"))
        contains_stem_phrase = any(phrase in opt_a.lower() for phrase in stem_indicators)
        
        if (is_short_stem or ends_with_open) and (ends_with_colon or contains_stem_phrase):
            should_merge = True

    if should_merge:
        print(f"🔧 [Auto-Healing] Detected question stem split in Row. Merging Option A into Question stem...")
        merged_question = f"{question_text} {opt_a}".strip()
        healed["Question_Text"] = merged_question
        healed["Option_A"] = opt_b
        healed["Option_B"] = opt_c
        healed["Option_C"] = opt_d
        healed["Option_D"] = ""  # Shifted left
        
        # Adjust correct option ID if options shifted
        if correct_idx > 0:
            correct_idx -= 1
            inv_map = {0: "A", 1: "B", 2: "C", 3: "D"}
            healed["Correct_Option"] = inv_map.get(correct_idx, "A")
    
    return healed

def generate_mcq_image(data):
    try:
        print("[VERBOSE LOG] Generating 1080x1080 MCQ HTML template...")
        with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
            template = f.read()

        html_content = template \
            .replace("{{TARGET_EXAM}}", str(data.get("Target_Exam", ""))) \
            .replace("{{QUESTION_TEXT}}", str(data.get("Question_Text", ""))) \
            .replace("{{OPTION_A}}", str(data.get("Option_A", ""))) \
            .replace("{{OPTION_B}}", str(data.get("Option_B", ""))) \
            .replace("{{OPTION_C}}", str(data.get("Option_C", ""))) \
            .replace("{{OPTION_D}}", str(data.get("Option_D", "")))

        with open(TEMP_HTML_FILE, "w", encoding="utf-8") as f:
            f.write(html_content)

        print("[VERBOSE LOG] Rendering image via Playwright headless Chromium...")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1080, "height": 1080})
            
            file_url = f"file:///{TEMP_HTML_FILE.replace(os.sep, '/')}"
            page.goto(file_url, wait_until="networkidle")
            
            page.screenshot(path=OUTPUT_IMAGE_FILE)
            browser.close()

        print(f"✅ Image successfully generated at automations/output_mcq.png")

    except Exception as e:
        print(f"❌ Error generating image: {e}")
        raise e
    finally:
        if os.path.exists(TEMP_HTML_FILE):
            os.remove(TEMP_HTML_FILE)

def jaccard_similarity(str1: str, str2: str) -> float:
    words1 = set(re.findall(r'\w+', str1.lower()))
    words2 = set(re.findall(r'\w+', str2.lower()))
    if not words1 or not words2:
        return 0.0
    return len(words1 & words2) / len(words1 | words2)

def save_autonomous_mcq_to_history(mcq_row: dict):
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = []
    
    entry = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "exam": mcq_row.get("Target_Exam", "Odisha Competitive Exams"),
        "content_stage": "EXAM_SPECIFIC",
        "topic": "autonomous_mcq_" + datetime.now().strftime("%Y%m%d_%H%M%S"),
        "question": mcq_row.get("Question_Text", ""),
        "options": [
            mcq_row.get("Option_A", ""),
            mcq_row.get("Option_B", ""),
            mcq_row.get("Option_C", ""),
            mcq_row.get("Option_D", "")
        ],
        "correct_option_index": {"A": 0, "B": 1, "C": 2, "D": 3}.get(str(mcq_row.get("Correct_Option", "A")).upper(), 0),
        "explanation": mcq_row.get("Explanation", "")
    }
    history.append(entry)
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
        print(f"📁 Saved autonomous MCQ to history ({HISTORY_FILE}).")
    except Exception as e:
        print(f"⚠️ Failed to save history entry: {e}")

def generate_autonomous_mcq(target_exam: str = None) -> dict:
    """
    Autonomous Cognitive MCQ Generator with Frontier LLM Reasoning, Zero-Hallucination Grounding,
    and Anti-Leakage / Distractor Engineering.
    """
    EXAM_POOL = [
        "OSSC CGL (Combined Graduate Level)",
        "OPSC ASO (Assistant Section Officer)",
        "OSSSC CRE (RI, Amin, Forest Guard)",
        "Odisha Police SI & Constable",
        "OPSC Odisha Civil Services (OCS)",
        "BSE Odisha OTET / OSSTET"
    ]
    TOPIC_POOL = [
        {"subject": "Odisha State History, Heritage & Geography", "focus": "Ancient & Medieval dynasties (Bhauma-Kara, Somavamshi, Eastern Ganga, Gajapati), Paika Rebellion 1817, Salt Satyagraha at Inchudi, Major rivers (Mahanadi, Brahmani, Baitarani), and Ramsar wetlands."},
        {"subject": "Indian Polity & Constitutional Framework", "focus": "Fundamental Rights, DPSP, 73rd & 74th Constitutional Amendments, Election Commission, CAG, Finance Commission, and High Court / Subordinate Judiciary."},
        {"subject": "General Science & Environmental Ecology", "focus": "Optics, Laws of Motion, Chemical reactions & acids/bases, Human organ systems & nutrition, Wildlife Sanctuaries & National Parks of Odisha (Similipal, Bhitarkanika, Satkosia)."},
        {"subject": "Quantitative Aptitude & Number Systems", "focus": "LCM & HCF conceptual traps, Percentage changes, Profit & Loss discount tricks, Simple & Compound Interest, Time & Distance relative speed."},
        {"subject": "Odia & English Language Grammar Rules", "focus": "Odia Sandhi, Samasa, Krutanta, Tadhita, Krukari, Idioms (Rudhi & Lokabani), Subject-Verb agreement, and Prepositional idioms."}
    ]

    day_idx = datetime.now().timetuple().tm_yday
    chosen_exam = target_exam or EXAM_POOL[day_idx % len(EXAM_POOL)]
    chosen_topic = TOPIC_POOL[(day_idx + 1) % len(TOPIC_POOL)]

    published_stems = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                h_data = json.load(f)
                for item in h_data[-60:]:
                    q = item.get("question") or item.get("Question_Text")
                    if q:
                        published_stems.append(q)
        except Exception:
            pass

    history_ban_list = "\n".join([f"- {s}" for s in published_stems[-20:]]) if published_stems else "(None)"

    system_prompt = f"""You are the Chief Academic Paper Setter & Senior Content Specialist for Odisha Competitive Examinations (OPSC, OSSC, OSSSC).
Your task is to generate ONE ORIGINAL, HIGH-YIELD competitive exam multiple-choice question (MCQ) for {chosen_exam}.

Subject/Domain: {chosen_topic['subject']}
Focus Curriculum: {chosen_topic['focus']}

======================================================================
1. ZERO-HALLUCINATION & FACTUAL ACCURACY MANDATE
======================================================================
- The question stem, options, and explanation must be 100% FACTUALLY ACCURATE and grounded in official textbooks, standard reference works, statutory Acts, or government gazettes.
- Never invent imaginary historical events, fake government schemes, or distorted constitutional articles.
- Every metric, date, or provision must be authentic.

======================================================================
2. PEDAGOGICAL DISTRACTOR ENGINEERING (AUTHENTIC EXAM TRAPS)
======================================================================
- Provide exactly 4 options: Option A, Option B, Option C, Option D.
- One option is strictly correct.
- The 3 incorrect options (distractors) MUST represent genuine candidate traps:
  * Trap 1: A near-neighbor year, article, or term commonly confused by students.
  * Trap 2: A closely related entity, committee, river, or district.
  * Trap 3: A common arithmetic or grammatical sign/tense misconception.
- NO silly, unrealistic, or placeholder options.

======================================================================
3. TWO-PART COMPREHENSIVE EXPLANATION (UNDER 180 CHARACTERS)
======================================================================
In `Explanation`, provide:
1) Core Reason: Why the correct option is factually right.
2) Trap Breakdown: Why the primary distractor option is incorrect.
Keep the explanation under 180 characters for Telegram/YouTube display.

======================================================================
4. ANTI-LEAKAGE / NO REPEATS
DO NOT generate any question similar to these recently published questions:
{history_ban_list}

Return ONLY valid JSON matching this schema:
{{
  "Target_Exam": "{chosen_exam}",
  "Question_Text": "Clear, concise exam question stem?",
  "Option_A": "Option text A",
  "Option_B": "Option text B",
  "Option_C": "Option text C",
  "Option_D": "Option text D",
  "Correct_Option": "A" or "B" or "C" or "D",
  "Explanation": "Core reason why correct option is right. Trap breakdown why other is wrong."
}}
"""

    gemini_key = GEMINI_API_KEY
    api_key = DEEPSEEK_API_KEY

    GEMINI_MODELS = ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.6-flash", "gemini-3.7-flash", "gemini-3.8-flash", "gemini-3.1-flash-lite"]
    if gemini_key:
        for g_model in GEMINI_MODELS:
            try:
                print(f"🚀 [MCQEngine Autonomous] Calling Gemini ({g_model})...")
                g_url = f"https://generativelanguage.googleapis.com/v1beta/models/{g_model}:generateContent?key={gemini_key}"
                g_payload = {
                    "contents": [{"parts": [{"text": f"{system_prompt}\n\nCRITICAL: Output ONLY pure valid JSON."}]}],
                    "generationConfig": {
                        "response_mime_type": "application/json",
                        "temperature": 0.4,
                        "maxOutputTokens": 1000
                    }
                }
                g_res = requests.post(g_url, headers={"Content-Type": "application/json"}, json=g_payload, timeout=25)
                if g_res.ok:
                    data = g_res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        raw_c = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        from shared.ai_parser import parse_ai_json_response
                        parsed = parse_ai_json_response(raw_c)
                        if parsed and parsed.get("Question_Text") and parsed.get("Option_A"):
                            is_dup = False
                            for past_q in published_stems:
                                if jaccard_similarity(parsed["Question_Text"], past_q) > 0.55:
                                    print(f"⚠️ [MCQEngine Autonomous] Jaccard duplicate detected against: '{past_q[:40]}'.")
                                    is_dup = True
                                    break
                            if not is_dup:
                                print(f"✅ [MCQEngine Autonomous] Gemini ({g_model}) generated high-yield MCQ successfully.")
                                return parsed
            except Exception as ex:
                print(f"⚠️ [MCQEngine Autonomous] Gemini ({g_model}) note: {ex}")

    if api_key:
        try:
            print("🚀 [MCQEngine Autonomous] Invoking NVIDIA NIM fallback...")
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": "nvidia/nemotron-3-super-120b-a12b",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "Generate the exam-grade MCQ JSON now."}
                ],
                "temperature": 0.4,
                "max_tokens": 1000,
                "response_format": {"type": "json_object"}
            }
            res = requests.post(f"{DEEPSEEK_BASE_URL.rstrip('/')}/chat/completions", headers=headers, json=payload, timeout=30)
            if res.ok:
                from shared.ai_parser import parse_ai_json_response
                raw_c = res.json().get('choices', [{}])[0].get('message', {}).get('content', '')
                parsed = parse_ai_json_response(raw_c)
                if parsed and parsed.get("Question_Text") and parsed.get("Option_A"):
                    print("✅ [MCQEngine Autonomous] NVIDIA NIM generated MCQ successfully.")
                    return parsed
        except Exception as ex:
            print(f"⚠️ [MCQEngine Autonomous] NVIDIA NIM error: {ex}")

    print("ℹ️ [MCQEngine Autonomous] Deploying verified static syllabus reserve question.")
    return {
        "Target_Exam": chosen_exam,
        "Question_Text": "Under which Article of the Constitution of India is the Finance Commission constituted by the President?",
        "Option_A": "Article 280",
        "Option_B": "Article 243-I",
        "Option_C": "Article 324",
        "Option_D": "Article 356",
        "Correct_Option": "A",
        "Explanation": "Article 280 mandates Union Finance Commission. Art 243-I governs State Finance Commissions; Art 324 is Election Commission."
    }

from post_to_youtube import post_to_youtube

def main():
    print("==================================================")
    print(f"🚀 ODISHA MCQ ENGINE - RUNNER (Batch Size: {MCQ_BATCH_SIZE} MCQ/Run)")
    print("==================================================\n")

    try:
        sheet = None
        pending_items = []
        status_col_idx = 10
        is_autonomous = False

        try:
            sheet, pending_items, status_col_idx = fetch_pending_questions(limit=MCQ_BATCH_SIZE)
        except Exception as fetch_err:
            print(f"⚠️ Google Sheet access note: {fetch_err}. Activating Autonomous Cognitive Question Setter...")

        if not pending_items:
            print("💡 No pending questions in Google Sheet. Engaging Autonomous Cognitive Question Setter...")
            auto_mcq = generate_autonomous_mcq()
            if auto_mcq:
                pending_items = [(-1, auto_mcq)]
                is_autonomous = True
            else:
                print("❌ Autonomous MCQ generation yielded no valid question.")
                today_date_str = datetime.now().strftime("%d %B %Y %I:%M %p")
                admin_msg = (
                    f"🎯 <b>Daily MCQ Engine Execution Report</b> ⚠️\n\n"
                    f"📅 <b>Time:</b> {today_date_str}\n"
                    f"ℹ️ <b>Status:</b> No pending MCQs found and Autonomous Setter failed.\n"
                    f"🌐 <b>Website CTA:</b> Active ✅"
                )
                send_telegram_notification(TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_CHAT_ID, admin_msg)
                return

        total_batch = len(pending_items)
        processed_count = 0
        tg_success_count = 0
        yt_success_count = 0
        summary_details = []

        for row_index, raw_row in pending_items:
            current_num = processed_count + 1
            print(f"\n--------------------------------------------------")
            print(f"📝 Processing Question [{current_num}/{total_batch}] at Row {row_index}...")
            print(f"--------------------------------------------------")

            # Auto-heal and normalize data before rendering or dispatching
            row = normalize_and_heal_mcq(raw_row)

            generate_mcq_image(row)

            target_exam = str(row.get("Target_Exam", "")).strip()
            question_text = str(row.get("Question_Text", "")).strip()
            
            # Formatting question text with length clamp
            if total_batch > 1:
                full_question = f"[{current_num}/{total_batch}] [{target_exam}] {question_text}" if target_exam else f"[{current_num}/{total_batch}] {question_text}"
            else:
                full_question = f"[{target_exam}] {question_text}" if target_exam else question_text

            if len(full_question) > 300:
                full_question = full_question[:297].rstrip() + "..."

            options = [
                str(row.get("Option_A", "")).strip(),
                str(row.get("Option_B", "")).strip(),
                str(row.get("Option_C", "")).strip(),
                str(row.get("Option_D", "")).strip()
            ]
            options = [opt for opt in options if opt]

            correct_raw = str(row.get("Correct_Option", "A")).strip().upper()
            mapping = {"A": 0, "B": 1, "C": 2, "D": 3, "1": 0, "2": 1, "3": 2, "4": 3}
            correct_option_id = mapping.get(correct_raw, 0)
            explanation = str(row.get("Explanation", "")).strip()

            # Step 1: Dispatch Native Quiz Poll to Public Channel
            tg_success = send_telegram_quiz_poll(
                TELEGRAM_BOT_TOKEN,
                TELEGRAM_CHAT_ID,
                full_question,
                options,
                correct_option_id,
                explanation=explanation
            )

            # Step 1B: Visual Card Fallback if native poll failed
            if not tg_success:
                print("⚠️ Native Telegram Quiz Poll failed. Initiating Visual Card Fallback to channel...")
                opt_lines = "\n".join([f"<b>{chr(65+i)})</b> {opt}" for i, opt in enumerate(options)])
                fallback_caption = (
                    f"🎯 <b>Daily Practice Question</b>\n"
                    f"🏆 <b>Exam:</b> {target_exam or 'Odisha Govt Exams'}\n\n"
                    f"❓ <b>Question:</b>\n{question_text}\n\n"
                    f"{opt_lines}\n\n"
                    f"💡 <i>Comment your answer below! Practice full mock tests & download PDF notes:</i>\n"
                    f"👉 <b>https://www.odishaexamprep.in/</b>"
                )
                fallback_res = send_telegram_notification(
                    TELEGRAM_BOT_TOKEN,
                    TELEGRAM_CHAT_ID,
                    fallback_caption[:1024],
                    image_path=OUTPUT_IMAGE_FILE if os.path.exists(OUTPUT_IMAGE_FILE) else None
                )
                if fallback_res:
                    print("✅ Visual Card Fallback successfully posted to Telegram Channel!")
                    tg_success = True

            if tg_success:
                tg_success_count += 1

            # Step 2: Post to YouTube Community (wrapped safely so YouTube error never blocks Sheet status update)
            try:
                yt_success = post_to_youtube(row)
                if yt_success:
                    yt_success_count += 1
            except Exception as yt_err:
                print(f"⚠️ YouTube Community posting error (non-fatal): {yt_err}")
                yt_success = False

            # Step 3: Update Google Sheet Status ONLY IF PUBLISHED (or save to history if autonomous)
            if row_index == -1:
                if tg_success or yt_success:
                    save_autonomous_mcq_to_history(row)
                    print("✅ Autonomous MCQ saved to published history.")
            elif tg_success or yt_success:
                if sheet:
                    def _update_sheet_row():
                        sheet.update_cell(row_index, status_col_idx, 'Published')

                    try:
                        retry_google_api(_update_sheet_row, max_retries=4, initial_delay=2, action_name=f"Update Row {row_index} Status")
                        print(f"✅ Google Sheet row {row_index} status updated to 'Published' (Col {status_col_idx})")
                    except Exception as cell_err:
                        print(f"⚠️ Warning: Could not update status in Google Sheet for row {row_index}: {cell_err}")
            else:
                if row_index != -1 and sheet:
                    print(f"❌ Row {row_index} was NOT published to Telegram or YouTube. Preserving status as 'Failed - Retry'.")
                    def _mark_sheet_failed():
                        sheet.update_cell(row_index, status_col_idx, 'Failed - Retry')
                    try:
                        retry_google_api(_mark_sheet_failed, max_retries=3, initial_delay=2, action_name=f"Mark Row {row_index} Failed")
                    except Exception:
                        pass

            processed_count += 1

            status_icon = "✅" if tg_success else "❌"
            summary_details.append(f"• <b>Row {row_index} [{target_exam}]:</b> {status_icon} {question_text[:45]}...")
            time.sleep(2)

        # Step 4: Dispatch Daily 5-MCQ Quiz Set Completion Banner with 7-Day Rotational Student Image (student 1.png - student 7.png)
        if processed_count > 1 and tg_success_count > 0:
            # 7-Day Rotational Student Image Index (1 to 7)
            # Monday=1, Tuesday=2, Wednesday=3, Thursday=4, Friday=5, Saturday=6, Sunday=7
            day_index = (datetime.now().weekday() % 7) + 1
            student_img_filename = f"student {day_index}.png"
            student_image_path = os.path.join(SCRIPT_DIR, student_img_filename)
            if not os.path.exists(student_image_path):
                student_image_path = os.path.join(SCRIPT_DIR, "student 1.png")

            print(f"[VERBOSE LOG] Attaching Rotational Student Image for Day {day_index}: {student_img_filename}")

            completion_banner = (
                f"🎉 <b>TODAY'S DAILY 5-MCQ QUIZ SET COMPLETED!</b>\n\n"
                f"📅 <b>Daily Schedule:</b> New 5-MCQ Sets posted every morning at 10:00 AM IST.\n"
                f"🏆 <b>Target Exams:</b> OPSC ASO, OSSC CGL, OSSSC RI, Police SI & Railway RRB.\n\n"
                f"🚀 <b>READY FOR FULL MOCK TESTS & PDF NOTES?</b>\n"
                f"Practice 500+ speed tests, chapter-wise MCQs & study material on our official website:\n"
                f"👉 <b>https://www.odishaexamprep.in/</b>\n\n"
                f"📺 <b>SUBSCRIBE ON YOUTUBE FOR VIDEO CLASSES:</b>\n"
                f"👉 <b>https://www.youtube.com/@OdishaExamPrep365</b>"
            )
            send_telegram_notification(
                TELEGRAM_BOT_TOKEN,
                TELEGRAM_CHAT_ID,
                completion_banner,
                image_path=student_image_path if os.path.exists(student_image_path) else None
            )

        # Step 5: Dispatch Summary Execution Report to Admin Chat ONLY
        last_item = pending_items[-1][1]
        last_item_healed = normalize_and_heal_mcq(last_item)
        generate_mcq_image(last_item_healed)

        tg_status_str = f"Published to Channel ✅ ({tg_success_count}/{processed_count} Dispatches)" if tg_success_count > 0 else "Failed ❌"
        yt_status_str = f"Published to YouTube Community ✅ ({yt_success_count}/{processed_count} Posts)" if yt_success_count > 0 else "Skipped / Pending Setup ⚠️"
        sheet_status_str = "Status updated to 'Published' ✅" if (tg_success_count > 0 or yt_success_count > 0) else "Status retained as 'Failed - Retry' ⚠️"

        admin_summary_msg = (
            f"🎯 <b>Daily MCQ Engine Execution Report</b>\n\n"
            f"📊 <b>MCQs Processed Today:</b> {processed_count} Questions\n\n"
            f"📢 <b>Telegram Channel:</b> {tg_status_str}\n"
            f"🔴 <b>YouTube Community:</b> {yt_status_str}\n"
            f"📊 <b>Google Sheets:</b> {sheet_status_str}\n\n"
            f"<b>Questions Log:</b>\n" + "\n".join(summary_details) + "\n\n"
            f"🌐 <b>Website CTA:</b> Active"
        )

        send_telegram_notification(
            TELEGRAM_BOT_TOKEN,
            TELEGRAM_ADMIN_CHAT_ID,
            admin_summary_msg,
            image_path=OUTPUT_IMAGE_FILE
        )

        print(f"\n🎉 Daily MCQ Engine completed! (Telegram: {tg_success_count}/{processed_count}, YouTube: {yt_success_count}/{processed_count})")
        if processed_count > 0 and tg_success_count == 0 and yt_success_count == 0:
            print("❌ Failure: All dispatches failed for this run.")
            sys.exit(1)

    except SystemExit as se:
        sys.exit(se.code)
    except Exception as e:
        error_msg = f"❌ <b>MCQ Engine Automation Error</b>\n\nError details: <code>{str(e)}</code>"
        print(f"❌ Automation Error: {e}")
        try:
            send_telegram_notification(
                TELEGRAM_BOT_TOKEN,
                TELEGRAM_ADMIN_CHAT_ID,
                error_msg
            )
        except Exception:
            pass
        sys.exit(1)

if __name__ == "__main__":
    main()
