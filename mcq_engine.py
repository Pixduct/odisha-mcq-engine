import os
import sys
import json
import base64
import time
import re
import requests
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
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

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CREDS_FILE = os.path.join(SCRIPT_DIR, "google_credentials.json")
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
        
        raw_payload = {
            "chat_id": chat_id,
            "question": question[:300],
            "options": json.dumps(options),
            "is_anonymous": True,
            "type": "quiz",
            "correct_option_id": correct_option_id
        }
        if explanation:
            raw_payload["explanation"] = explanation[:200]
            raw_payload["explanation_parse_mode"] = "HTML"

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

from post_to_youtube import post_to_youtube

def main():
    print("==================================================")
    print(f"🚀 ODISHA MCQ ENGINE - RUNNER (Batch Size: {MCQ_BATCH_SIZE} MCQ/Run)")
    print("==================================================\n")

    try:
        sheet, pending_items, status_col_idx = fetch_pending_questions(limit=MCQ_BATCH_SIZE)
        if not pending_items:
            print("ℹ️ Execution complete: No pending questions to process.")
            today_date_str = datetime.now().strftime("%d %B %Y %I:%M %p")
            admin_msg = (
                f"🎯 <b>Daily MCQ Engine Execution Report</b> ℹ️\n\n"
                f"📅 <b>Time:</b> {today_date_str}\n"
                f"ℹ️ <b>Status:</b> No pending MCQs found in Google Sheet (All questions published / up to date).\n"
                f"🌐 <b>Website CTA:</b> Active ✅"
            )
            send_telegram_notification(TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_CHAT_ID, admin_msg)
            return

        total_batch = len(pending_items)
        processed_count = 0
        tg_success_count = 0
        yt_success_count = 0
        summary_details = []

        for row_index, row in pending_items:
            current_num = processed_count + 1
            print(f"\n--------------------------------------------------")
            print(f"📝 Processing Question [{current_num}/{total_batch}] at Row {row_index}...")
            print(f"--------------------------------------------------")

            generate_mcq_image(row)

            target_exam = str(row.get("Target_Exam", "")).strip()
            question_text = str(row.get("Question_Text", "")).strip()
            
            # Formatting question text
            if total_batch > 1:
                full_question = f"[{current_num}/{total_batch}] [{target_exam}] {question_text}" if target_exam else f"[{current_num}/{total_batch}] {question_text}"
            else:
                full_question = f"[{target_exam}] {question_text}" if target_exam else question_text

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
            
            # High-converting CTA inside poll explanation bubble
            site_cta = (
                "🎯 Daily MCQ Practice (Morning • Afternoon • Evening Live Sets 🚀)\n"
                "🌐 Practice 500+ Full Mock Tests & PDFs:\n"
                "👉 https://www.odishaexamprep.in/\n\n"
                "📺 Join YouTube Channel for Video Classes:\n"
                "👉 https://www.youtube.com/@OdishaExamPrep365"
            )
            poll_explanation = f"{explanation}\n\n{site_cta}" if explanation else site_cta

            # Step 1: Dispatch Native Quiz Poll ONLY to Public Channel
            tg_success = send_telegram_quiz_poll(
                TELEGRAM_BOT_TOKEN,
                TELEGRAM_CHAT_ID,
                full_question,
                options,
                correct_option_id,
                explanation=poll_explanation
            )
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

            # Step 3: Update Google Sheet Status with retry protection
            def _update_sheet_row():
                sheet.update_cell(row_index, status_col_idx, 'Published')

            try:
                retry_google_api(_update_sheet_row, max_retries=4, initial_delay=2, action_name=f"Update Row {row_index} Status")
                print(f"✅ Google Sheet row {row_index} status updated to 'Published' (Col {status_col_idx})")
            except Exception as cell_err:
                print(f"⚠️ Warning: Could not update status in Google Sheet for row {row_index}: {cell_err}")

            processed_count += 1

            summary_details.append(f"• <b>Row {row_index} [{target_exam}]:</b> {question_text[:45]}...")
            time.sleep(2)

        # Step 4: Dispatch Daily 5-MCQ Quiz Set Completion Banner with 7-Day Rotational Student Image (student 1.png - student 7.png)
        if processed_count > 1:
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
        generate_mcq_image(last_item)

        tg_status_str = f"Published to Channel ✅ ({tg_success_count}/{processed_count} Quiz Polls)" if tg_success_count > 0 else "Failed ❌"
        yt_status_str = f"Published to YouTube Community ✅ ({yt_success_count}/{processed_count} Posts)" if yt_success_count > 0 else "Skipped / Pending Setup ⚠️"

        admin_summary_msg = (
            f"🎯 <b>Daily MCQ Engine Execution Report</b>\n\n"
            f"📊 <b>MCQs Processed Today:</b> {processed_count} Questions\n\n"
            f"📢 <b>Telegram Channel:</b> {tg_status_str}\n"
            f"🔴 <b>YouTube Community:</b> {yt_status_str}\n"
            f"📊 <b>Google Sheets:</b> Status updated to 'Published' ✅\n\n"
            f"<b>Published Questions:</b>\n" + "\n".join(summary_details) + "\n\n"
            f"🌐 <b>Website CTA:</b> Active"
        )

        send_telegram_notification(
            TELEGRAM_BOT_TOKEN,
            TELEGRAM_ADMIN_CHAT_ID,
            admin_summary_msg,
            image_path=OUTPUT_IMAGE_FILE
        )

        print(f"\n🎉 Daily MCQ Engine completed! Published {processed_count} MCQs successfully.")

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
