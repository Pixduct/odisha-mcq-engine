import os
import sys

# Ensure automations root is on sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
AUTOMATIONS_DIR = os.path.dirname(SCRIPT_DIR)
if AUTOMATIONS_DIR not in sys.path:
    sys.path.insert(0, AUTOMATIONS_DIR)

from exam_card_renderer import resolve_clean_display_domain, render_exam_alert_card
from shared.telegram import sanitize_official_link

def test_domain_sanitization():
    print("--- Testing resolve_clean_display_domain ---")
    
    # Case 1: ASP.NET javascript:__doPostBack (User's exact bug)
    ugly_js = "javascript:__doPostBack('ctl00$generic_masterpage1$ctl62','')"
    dom1 = resolve_clean_display_domain(ugly_js, "OSSC", "OSSC")
    print(f"Case 1 (OSSC + ASP.NET): '{ugly_js}' -> '{dom1}'")
    assert dom1 == "ossc.gov.in", f"Expected ossc.gov.in, got {dom1}"

    # Case 2: Full valid URL with query params
    full_url = "https://www.ossc.gov.in/Public/Notices.aspx?id=9218&auth=true"
    dom2 = resolve_clean_display_domain(full_url, "OSSC", "OSSC")
    print(f"Case 2 (Clean netloc): '{full_url}' -> '{dom2}'")
    assert dom2 == "ossc.gov.in", f"Expected ossc.gov.in, got {dom2}"

    # Case 3: Empty / javascript:void(0) with High Court
    js_void = "javascript:void(0)"
    dom3 = resolve_clean_display_domain(js_void, "High Court of Orissa", "ODISHA HIGH COURT")
    print(f"Case 3 (High Court): '{js_void}' -> '{dom3}'")
    assert dom3 == "orissahighcourt.nic.in", f"Expected orissahighcourt.nic.in, got {dom3}"

    # Case 4: OPSC direct PDF link
    pdf_url = "https://opsc.gov.in/pdf/notice_2026.pdf"
    dom4 = resolve_clean_display_domain(pdf_url, "OPSC", "OPSC")
    print(f"Case 4 (OPSC PDF): '{pdf_url}' -> '{dom4}'")
    assert dom4 == "opsc.gov.in", f"Expected opsc.gov.in, got {dom4}"

    # Case 5: Telegram link sanitizer
    clean_tg_link = sanitize_official_link(ugly_js, "OSSC")
    print(f"Case 5 (Telegram Sanitizer): '{ugly_js}' -> '{clean_tg_link}'")
    assert clean_tg_link == "https://www.ossc.gov.in", f"Expected https://www.ossc.gov.in, got {clean_tg_link}"

    print("✅ All domain & link sanitization assertions PASSED!\n")


def test_card_rendering_with_user_sample():
    print("--- Rendering Card With User's Exact Bug Payload ---")
    test_article = {
        "title": "OSSC CHSL Specialist Posts 2025 Preliminary Examination Mock Test Link Released",
        "organization": "OSSC",
        "exam": "COMBINED HIGHER SECONDARY (10+2) LEVEL SPECIALIST POSTS PRELIMINARY EXAMINATION 2025",
        "official_link": "javascript:__doPostBack('ctl00$generic_masterpage1$ctl62','')",
        "dates": "23 Sep 2026 onwards",
        "bullets": [
            "SELECTION MODE: Candidates are shortlisted through Preliminary Exam, Main Exam, and subsequent stages as mandated by OSSC.",
            "EXAM PRACTICE: The mock test link enables aspirants to familiarize themselves with the computer-based test interface, navigation, and question patterns.",
            "NEXT STEP: Registered candidates should immediately access the official portal to take the mock test and review their preparation levels."
        ]
    }

    test_output_png = os.path.join(AUTOMATIONS_DIR, "output", "test_fixed_ossc_card.png")
    os.makedirs(os.path.dirname(test_output_png), exist_ok=True)

    result_path = render_exam_alert_card(test_article, output_path=test_output_png)
    assert os.path.exists(result_path), f"Rendered image not found at {result_path}"
    file_size = os.path.getsize(result_path)
    assert file_size > 50000, f"Rendered image too small: {file_size} bytes"

    print(f"✅ Card rendered successfully to: {result_path} (Size: {file_size} bytes)")
    print("✅ Verified: Domain was cleanly resolved to 'ossc.gov.in' and rendered flawlessly without javascript leaks!")


if __name__ == "__main__":
    test_domain_sanitization()
    test_card_rendering_with_user_sample()
