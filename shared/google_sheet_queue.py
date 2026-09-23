import os
import sys
import json
import time
from typing import Optional, Dict, Any, Tuple, List

try:
    import gspread
    from google.oauth2.service_account import Credentials
except ImportError:
    gspread = None
    Credentials = None

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDS_FILE = os.path.join(SCRIPT_DIR, "google_credentials.json")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def retry_google_api(func, max_retries=5, initial_delay=3, backoff_factor=2, action_name="Google Sheet Operation"):
    delay = initial_delay
    last_exception = None
    for attempt in range(1, max_retries + 1):
        try:
            return func()
        except Exception as e:
            last_exception = e
            print(f"[Google Sheet Queue] {action_name} attempt {attempt}/{max_retries} note: {e}")
            if attempt < max_retries:
                time.sleep(delay)
                delay *= backoff_factor
    raise last_exception

def get_google_sheet_client():
    if not gspread or not Credentials:
        print("[Google Sheet Queue] gspread or google.oauth2 not installed.")
        return None

    creds_json_str = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if creds_json_str:
        creds_dict = json.loads(creds_json_str)
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    elif os.path.exists(CREDS_FILE):
        creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
    else:
        print("ℹ️ [Google Sheet Queue] No google_credentials.json or GOOGLE_CREDENTIALS_JSON found.")
        return None

    return gspread.authorize(creds)

def fetch_pending_editorial_row(
    sheet_name: str = "Odisha_Editorial_Queue",
    tab_name: Optional[str] = None
) -> Tuple[Optional[Any], Optional[int], Optional[Dict[str, Any]]]:
    """
    Fetches the first pending row from the Google Sheet Editorial Queue.
    Returns: (sheet_obj, row_index, row_dict)
    Expected Columns:
    - Target_Exam (or Exam / Category)
    - Title (or Article_Title)
    - Image_URL (or Image / Cover_Image)
    - Focus_Notes (or Notes / Keywords)
    - Status (Pending / Published)
    - Published_URL
    - Published_At
    """
    try:
        client = get_google_sheet_client()
        if not client:
            return None, None, None

        # Fallback names to check
        possible_sheet_names = [
            "Odisha_Editorial_Queue .xlsx",
            "Odisha_Editorial_Queue.xlsx",
            "Odisha_Editorial_Queue",
            "Odisha_Editorial_Queue ",
            sheet_name,
            f"{sheet_name}.xlsx",
            f"{sheet_name} .xlsx",
            "Odisha_Blog_Queue.xlsx",
            "Odisha_Blog_Queue",
            "Odisha_MCQ_Engine",
            "OdishaExamPrep_Queue"
        ]
        spreadsheet = None

        for s_name in possible_sheet_names:
            try:
                spreadsheet = client.open(s_name)
                print(f"[Google Sheet Queue] Connected to Spreadsheet: '{s_name}'")
                break
            except Exception:
                continue

        if not spreadsheet:
            try:
                all_sheets = client.openall()
                for s in all_sheets:
                    title_low = s.title.lower()
                    if "editorial" in title_low or "blog" in title_low or "queue" in title_low:
                        spreadsheet = s
                        print(f"[Google Sheet Queue] Auto-discovered Spreadsheet: '{s.title}'")
                        break
            except Exception as e:
                print(f"[Google Sheet Queue] Auto-discovery note: {e}")

        if not spreadsheet:
            print(f"[Google Sheet Queue] Could not find any matching spreadsheet: {possible_sheet_names}")
            return None, None, None

        # Select worksheet
        sheet = None
        if tab_name:
            try:
                sheet = spreadsheet.worksheet(tab_name)
            except Exception:
                sheet = None

        if not sheet:
            ws_map = {ws.title.lower().strip(): ws for ws in spreadsheet.worksheets()}
            if "blog content" in ws_map:
                sheet = ws_map["blog content"]
            elif "blog_content" in ws_map:
                sheet = ws_map["blog_content"]
            elif "editorial_queue" in ws_map:
                sheet = ws_map["editorial_queue"]
            elif "editorial queue" in ws_map:
                sheet = ws_map["editorial queue"]
            elif "blog_queue" in ws_map:
                sheet = ws_map["blog_queue"]
            elif "blogs" in ws_map:
                sheet = ws_map["blogs"]
            elif "blog" in ws_map:
                sheet = ws_map["blog"]
            else:
                sheet = spreadsheet.sheet1

        def _fetch_records():
            return sheet.get_all_records()

        records = retry_google_api(_fetch_records, max_retries=3, action_name="Read Sheet Records")
        print(f"[Google Sheet Queue] Total rows found in '{sheet.title}': {len(records)}")

        for row_index, row in enumerate(records, start=2):
            status = str(row.get("Status") or row.get("status") or "").strip().lower()
            title = str(
                row.get("Title") or 
                row.get("Article_Title") or 
                row.get("Article Title") or 
                row.get("title") or ""
            ).strip()

            # If title exists and not already published
            if title and status not in ["published", "done", "completed", "live"]:
                target_exam = str(
                    row.get("Target_Exam") or 
                    row.get("Target Exam") or 
                    row.get("Exam") or 
                    row.get("Category") or 
                    "OSSSC Nursing Officer"
                ).strip()
                image_url = str(
                    row.get("Image_URL") or 
                    row.get("Image URL") or 
                    row.get("Image") or 
                    row.get("Cover_Image") or 
                    row.get("Cover Image") or ""
                ).strip()
                focus_notes = str(
                    row.get("Focus_Notes") or 
                    row.get("Focus Notes") or 
                    row.get("Notes") or 
                    row.get("Keywords") or ""
                ).strip()

                normalized_row = {
                    "target_exam": target_exam,
                    "title": title,
                    "image_url": image_url,
                    "focus_notes": focus_notes,
                    "status": "Pending"
                }

                print(f"[Google Sheet Queue] Found PENDING row #{row_index}: '{title}' (Exam: {target_exam})")
                return sheet, row_index, normalized_row

        print("[Google Sheet Queue] All rows in sheet are marked as Published or empty.")
        return sheet, None, None

    except Exception as e:
        print(f"[Google Sheet Queue] Error connecting or reading sheet: {e}")
        return None, None, None

def mark_editorial_row_published(sheet, row_index: int, published_url: str):
    """
    Updates the Google Sheet row status to 'Published' and records the live article URL.
    Auto-creates header columns if they don't exist.
    """
    if not sheet or not row_index:
        return False

    def _update_row():
        raw_headers = sheet.row_values(1)
        headers = [h.lower().replace(" ", "_") for h in raw_headers]
        
        status_col = None
        url_col = None
        date_col = None

        for idx, h in enumerate(headers, start=1):
            if "status" in h:
                status_col = idx
            elif "published_url" in h or ("url" in h and "image" not in h) or ("link" in h and "image" not in h):
                url_col = idx
            elif "published_at" in h or "date" in h:
                date_col = idx

        # Auto-create missing headers
        col_count = max(len(raw_headers), 4)
        if not status_col:
            status_col = col_count + 1
            sheet.update_cell(1, status_col, "Status")
        if not url_col:
            url_col = status_col + 1
            sheet.update_cell(1, url_col, "Published_URL")
        if not date_col:
            date_col = url_col + 1
            sheet.update_cell(1, date_col, "Published_At")

        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        sheet.update_cell(row_index, status_col, "Published")
        sheet.update_cell(row_index, url_col, published_url)
        sheet.update_cell(row_index, date_col, now_str)
        return True

    try:
        retry_google_api(_update_row, max_retries=3, action_name="Update Row Status to Published")
        print(f"[Google Sheet Queue] Row #{row_index} updated to 'Published' with URL: {published_url}")
        return True
    except Exception as e:
        print(f"[Google Sheet Queue] Failed to update row #{row_index}: {e}")
        return False
