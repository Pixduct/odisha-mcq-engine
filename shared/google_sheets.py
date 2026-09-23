import os
import json
from typing import List, Tuple, Dict, Any
import gspread

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(SCRIPT_DIR, "..", "google_credentials.json")

def get_gspread_client():
    creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if creds_json:
        creds_dict = json.loads(creds_json)
        return gspread.service_account_from_dict(creds_dict)
    elif os.path.exists(CREDENTIALS_FILE):
        return gspread.service_account(filename=CREDENTIALS_FILE)
    else:
        raise FileNotFoundError("Google credentials JSON not found in environment or file.")

def fetch_pending_blog_rows(spreadsheet_title: str = "OdishaExamPrep_Automation_Master", sheet_name: str = "Blog_Posts") -> Tuple[Any, List[Tuple[int, Dict[str, Any]]]]:
    try:
        gc = get_gspread_client()
        sh = gc.open(spreadsheet_title)
        sheet = sh.worksheet(sheet_name)
        records = sheet.get_all_records()

        pending_items = []
        for idx, row in enumerate(records, start=2): # 1-indexed row header = row 1
            status = str(row.get("Status", "")).strip()
            content_mode = str(row.get("Content_Mode", "")).strip().upper()
            if status == "Pending" and content_mode == "AUTO":
                pending_items.append((idx, row))

        return sheet, pending_items
    except Exception as e:
        print(f"⚠️ Google Sheet fetch warning: {e}")
        return None, []

def update_sheet_row_status(sheet, row_idx: int, status: str, col_idx: int = 4):
    if sheet:
        try:
            sheet.update_cell(row_idx, col_idx, status)
            print(f"✅ Sheet row {row_idx} status updated to '{status}'")
        except Exception as e:
            print(f"⚠️ Failed to update sheet row {row_idx}: {e}")
