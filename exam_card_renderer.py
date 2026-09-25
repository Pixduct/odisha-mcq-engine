import os
import sys
import re
import urllib.parse
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = SCRIPT_DIR

# ==============================================================================
# SCENARIO-ADAPTIVE VISUAL THEMES FOR EXAM NOTIFICATIONS
# ==============================================================================
# 20 APPROVED EXAM NOTIFICATION CATEGORIES & VISUAL THEMES CONFIGURATION
# ==============================================================================
EXAM_CATEGORIES_CONFIG = {
    1: {
        "id": "EXAM_NOTIFICATION_RELEASED",
        "name": "Exam Notification / Official Notification Released",
        "badge_text": "📢 OFFICIAL NOTIFICATION RELEASED",
        "badge_gradient": "linear-gradient(135deg, #2563EB, #1D4ED8)",
        "bg_color": "#0B1120",
        "radial_1": "rgba(37, 99, 235, 0.45)",
        "radial_2": "rgba(99, 102, 241, 0.25)",
        "card_bg": "linear-gradient(145deg, rgba(15, 23, 42, 0.95), rgba(10, 15, 30, 0.98))",
        "border_color": "#3B82F6",
        "accent_color": "#60A5FA",
        "glow_color": "rgba(37, 99, 235, 0.35)",
        "bullet_icon": "📢"
    },
    2: {
        "id": "APPLICATION_FORM_START",
        "name": "Application Form Start",
        "badge_text": "🚀 APPLICATION FORM START",
        "badge_gradient": "linear-gradient(135deg, #059669, #047857)",
        "bg_color": "#061A14",
        "radial_1": "rgba(5, 150, 105, 0.45)",
        "radial_2": "rgba(16, 185, 129, 0.25)",
        "card_bg": "linear-gradient(145deg, rgba(6, 40, 30, 0.95), rgba(4, 25, 20, 0.98))",
        "border_color": "#10B981",
        "accent_color": "#34D399",
        "glow_color": "rgba(5, 150, 105, 0.35)",
        "bullet_icon": "🚀"
    },
    3: {
        "id": "APPLICATION_LAST_DATE",
        "name": "Application Form Last Date",
        "badge_text": "⏳ APPLICATION LAST DATE",
        "badge_gradient": "linear-gradient(135deg, #D97706, #B45309)",
        "bg_color": "#1C1103",
        "radial_1": "rgba(217, 119, 6, 0.45)",
        "radial_2": "rgba(245, 158, 11, 0.25)",
        "card_bg": "linear-gradient(145deg, rgba(45, 25, 6, 0.95), rgba(30, 15, 4, 0.98))",
        "border_color": "#F59E0B",
        "accent_color": "#FBBF24",
        "glow_color": "rgba(217, 119, 6, 0.35)",
        "bullet_icon": "⏳"
    },
    4: {
        "id": "LAST_DATE_EXTENDED",
        "name": "Last Date Extended",
        "badge_text": "🔄 LAST DATE EXTENDED",
        "badge_gradient": "linear-gradient(135deg, #0891B2, #0E7490)",
        "bg_color": "#04151D",
        "radial_1": "rgba(8, 145, 178, 0.45)",
        "radial_2": "rgba(6, 182, 212, 0.25)",
        "card_bg": "linear-gradient(145deg, rgba(8, 38, 50, 0.95), rgba(4, 24, 32, 0.98))",
        "border_color": "#06B6D4",
        "accent_color": "#22D3EE",
        "glow_color": "rgba(8, 145, 178, 0.35)",
        "bullet_icon": "🔄"
    },
    5: {
        "id": "CORRECTION_WINDOW",
        "name": "Correction Window Open / Extended",
        "badge_text": "✏️ CORRECTION WINDOW OPEN",
        "badge_gradient": "linear-gradient(135deg, #7C3AED, #6D28D9)",
        "bg_color": "#130826",
        "radial_1": "rgba(124, 58, 237, 0.45)",
        "radial_2": "rgba(139, 92, 246, 0.25)",
        "card_bg": "linear-gradient(145deg, rgba(32, 14, 62, 0.95), rgba(20, 8, 40, 0.98))",
        "border_color": "#8B5CF6",
        "accent_color": "#A78BFA",
        "glow_color": "rgba(124, 58, 237, 0.35)",
        "bullet_icon": "✏️"
    },
    6: {
        "id": "ADMIT_CARD_RELEASED",
        "name": "Admit Card Released",
        "badge_text": "🎟️ ADMIT CARD RELEASED",
        "badge_gradient": "linear-gradient(135deg, #0284C7, #0369A1)",
        "bg_color": "#071422",
        "radial_1": "rgba(2, 132, 199, 0.50)",
        "radial_2": "rgba(56, 189, 248, 0.30)",
        "card_bg": "linear-gradient(145deg, rgba(10, 32, 54, 0.95), rgba(5, 18, 32, 0.98))",
        "border_color": "#38BDF8",
        "accent_color": "#7DD3FC",
        "glow_color": "rgba(2, 132, 199, 0.40)",
        "bullet_icon": "🎟️"
    },
    7: {
        "id": "EXAM_DATE_ANNOUNCED",
        "name": "Exam Date Announced",
        "badge_text": "📅 EXAM DATE ANNOUNCED",
        "badge_gradient": "linear-gradient(135deg, #4F46E5, #4338CA)",
        "bg_color": "#0D0E25",
        "radial_1": "rgba(79, 70, 229, 0.45)",
        "radial_2": "rgba(99, 102, 241, 0.25)",
        "card_bg": "linear-gradient(145deg, rgba(22, 24, 60, 0.95), rgba(12, 14, 38, 0.98))",
        "border_color": "#6366F1",
        "accent_color": "#818CF8",
        "glow_color": "rgba(79, 70, 229, 0.35)",
        "bullet_icon": "📅"
    },
    8: {
        "id": "EXAM_DATE_RESCHEDULED",
        "name": "Exam Date Changed / Rescheduled",
        "badge_text": "⚠️ EXAM DATE RESCHEDULED",
        "badge_gradient": "linear-gradient(135deg, #EA580C, #C2410C)",
        "bg_color": "#1C0D05",
        "radial_1": "rgba(234, 88, 12, 0.45)",
        "radial_2": "rgba(249, 115, 22, 0.25)",
        "card_bg": "linear-gradient(145deg, rgba(46, 20, 8, 0.95), rgba(28, 12, 5, 0.98))",
        "border_color": "#F97316",
        "accent_color": "#FB923C",
        "glow_color": "rgba(234, 88, 12, 0.35)",
        "bullet_icon": "⚠️"
    },
    9: {
        "id": "EXAM_CANCELLED_POSTPONED",
        "name": "Exam Cancelled / Postponed",
        "badge_text": "🚫 EXAM CANCELLED / POSTPONED",
        "badge_gradient": "linear-gradient(135deg, #E11D48, #BE123C)",
        "bg_color": "#1F080F",
        "radial_1": "rgba(225, 29, 72, 0.45)",
        "radial_2": "rgba(244, 63, 94, 0.25)",
        "card_bg": "linear-gradient(145deg, rgba(48, 14, 24, 0.95), rgba(30, 8, 15, 0.98))",
        "border_color": "#F43F5E",
        "accent_color": "#FDA4AF",
        "glow_color": "rgba(225, 29, 72, 0.35)",
        "bullet_icon": "🚫"
    },
    10: {
        "id": "EXAM_CITY_INTIMATION",
        "name": "Exam City / Centre Intimation",
        "badge_text": "📍 EXAM CITY / CENTRE INTIMATION",
        "badge_gradient": "linear-gradient(135deg, #0D9488, #0F766E)",
        "bg_color": "#051716",
        "radial_1": "rgba(13, 148, 136, 0.45)",
        "radial_2": "rgba(20, 184, 166, 0.25)",
        "card_bg": "linear-gradient(145deg, rgba(8, 38, 36, 0.95), rgba(5, 24, 22, 0.98))",
        "border_color": "#14B8A6",
        "accent_color": "#2DD4BF",
        "glow_color": "rgba(13, 148, 136, 0.35)",
        "bullet_icon": "📍"
    },
    11: {
        "id": "ANSWER_KEY_RELEASED",
        "name": "Answer Key Released",
        "badge_text": "🔑 ANSWER KEY RELEASED",
        "badge_gradient": "linear-gradient(135deg, #CA8A04, #A16207)",
        "bg_color": "#1A1503",
        "radial_1": "rgba(202, 138, 4, 0.45)",
        "radial_2": "rgba(234, 179, 8, 0.25)",
        "card_bg": "linear-gradient(145deg, rgba(42, 34, 8, 0.95), rgba(26, 20, 5, 0.98))",
        "border_color": "#EAB308",
        "accent_color": "#FDE047",
        "glow_color": "rgba(202, 138, 4, 0.35)",
        "bullet_icon": "🔑"
    },
    12: {
        "id": "ANSWER_KEY_REVISED",
        "name": "Answer Key Revised / Final Answer Key",
        "badge_text": "✨ FINAL ANSWER KEY RELEASED",
        "badge_gradient": "linear-gradient(135deg, #B45309, #92400E)",
        "bg_color": "#1B1204",
        "radial_1": "rgba(180, 83, 9, 0.45)",
        "radial_2": "rgba(217, 119, 6, 0.25)",
        "card_bg": "linear-gradient(145deg, rgba(42, 26, 8, 0.95), rgba(26, 16, 5, 0.98))",
        "border_color": "#D97706",
        "accent_color": "#FCD34D",
        "glow_color": "rgba(180, 83, 9, 0.35)",
        "bullet_icon": "✨"
    },
    13: {
        "id": "OBJECTION_WINDOW",
        "name": "Objection Window Open / Extended",
        "badge_text": "📝 OBJECTION WINDOW OPEN",
        "badge_gradient": "linear-gradient(135deg, #C2410C, #9A3412)",
        "bg_color": "#1A0E06",
        "radial_1": "rgba(194, 65, 12, 0.45)",
        "radial_2": "rgba(234, 88, 12, 0.25)",
        "card_bg": "linear-gradient(145deg, rgba(44, 22, 10, 0.95), rgba(26, 13, 6, 0.98))",
        "border_color": "#EA580C",
        "accent_color": "#FDBA74",
        "glow_color": "rgba(194, 65, 12, 0.35)",
        "bullet_icon": "📝"
    },
    14: {
        "id": "RESULT_RELEASED",
        "name": "Result Released",
        "badge_text": "🏆 RESULT DECLARED",
        "badge_gradient": "linear-gradient(135deg, #047857, #065F46)",
        "bg_color": "#051812",
        "radial_1": "rgba(4, 120, 87, 0.55)",
        "radial_2": "rgba(16, 185, 129, 0.35)",
        "card_bg": "linear-gradient(145deg, rgba(6, 42, 30, 0.95), rgba(3, 26, 18, 0.98))",
        "border_color": "#10B981",
        "accent_color": "#6EE7B7",
        "glow_color": "rgba(4, 120, 87, 0.45)",
        "bullet_icon": "🏆"
    },
    15: {
        "id": "CUTOFF_MERIT_LIST",
        "name": "Cut-off / Merit List Released",
        "badge_text": "📊 CUT-OFF & MERIT LIST",
        "badge_gradient": "linear-gradient(135deg, #065F46, #044E39)",
        "bg_color": "#041611",
        "radial_1": "rgba(6, 95, 70, 0.50)",
        "radial_2": "rgba(52, 211, 153, 0.25)",
        "card_bg": "linear-gradient(145deg, rgba(6, 38, 28, 0.95), rgba(3, 24, 17, 0.98))",
        "border_color": "#34D399",
        "accent_color": "#A7F3D0",
        "glow_color": "rgba(6, 95, 70, 0.40)",
        "bullet_icon": "📊"
    },
    16: {
        "id": "SCORECARD_RELEASED",
        "name": "Scorecard Released",
        "badge_text": "📈 SCORECARD RELEASED",
        "badge_gradient": "linear-gradient(135deg, #6366F1, #4F46E5)",
        "bg_color": "#0C0E24",
        "radial_1": "rgba(99, 102, 241, 0.45)",
        "radial_2": "rgba(129, 140, 248, 0.25)",
        "card_bg": "linear-gradient(145deg, rgba(20, 24, 58, 0.95), rgba(12, 14, 38, 0.98))",
        "border_color": "#818CF8",
        "accent_color": "#C7D2FE",
        "glow_color": "rgba(99, 102, 241, 0.35)",
        "bullet_icon": "📈"
    },
    17: {
        "id": "DOCUMENT_VERIFICATION",
        "name": "Document Verification / Counselling Schedule",
        "badge_text": "📑 DOCUMENT VERIFICATION SCHEDULE",
        "badge_gradient": "linear-gradient(135deg, #9333EA, #7E22CE)",
        "bg_color": "#170826",
        "radial_1": "rgba(147, 51, 234, 0.45)",
        "radial_2": "rgba(192, 132, 252, 0.25)",
        "card_bg": "linear-gradient(145deg, rgba(38, 14, 62, 0.95), rgba(24, 8, 40, 0.98))",
        "border_color": "#C084FC",
        "accent_color": "#E9D5FF",
        "glow_color": "rgba(147, 51, 234, 0.35)",
        "bullet_icon": "📑"
    },
    18: {
        "id": "INTERVIEW_SKILL_TEST",
        "name": "Interview / Skill Test / Physical Test Date",
        "badge_text": "🎯 INTERVIEW & SKILL TEST DATE",
        "badge_gradient": "linear-gradient(135deg, #6D28D9, #5B21B6)",
        "bg_color": "#120722",
        "radial_1": "rgba(109, 40, 217, 0.45)",
        "radial_2": "rgba(168, 85, 247, 0.25)",
        "card_bg": "linear-gradient(145deg, rgba(32, 12, 56, 0.95), rgba(18, 7, 34, 0.98))",
        "border_color": "#A855F7",
        "accent_color": "#D8B4FE",
        "glow_color": "rgba(109, 40, 217, 0.35)",
        "bullet_icon": "🎯"
    },
    19: {
        "id": "FINAL_SELECTION_LIST",
        "name": "Final Selection List / Final Result",
        "badge_text": "👑 FINAL SELECTION LIST",
        "badge_gradient": "linear-gradient(135deg, #B45309, #047857)",
        "bg_color": "#12130A",
        "radial_1": "rgba(180, 83, 9, 0.50)",
        "radial_2": "rgba(16, 185, 129, 0.35)",
        "card_bg": "linear-gradient(145deg, rgba(36, 32, 12, 0.95), rgba(20, 24, 10, 0.98))",
        "border_color": "#F59E0B",
        "accent_color": "#FDE68A",
        "glow_color": "rgba(180, 83, 9, 0.40)",
        "bullet_icon": "👑"
    },
    20: {
        "id": "IMPORTANT_OFFICIAL_NOTICE",
        "name": "Important Notice / Official Update",
        "badge_text": "📌 IMPORTANT OFFICIAL NOTICE",
        "badge_gradient": "linear-gradient(135deg, #DC2626, #B91C1C)",
        "bg_color": "#1C080B",
        "radial_1": "rgba(220, 38, 38, 0.45)",
        "radial_2": "rgba(239, 68, 68, 0.25)",
        "card_bg": "linear-gradient(145deg, rgba(46, 12, 18, 0.95), rgba(28, 8, 12, 0.98))",
        "border_color": "#EF4444",
        "accent_color": "#FCA5A5",
        "glow_color": "rgba(220, 38, 38, 0.35)",
        "bullet_icon": "📌"
    }
}

# Alias map for backwards compatibility with legacy strings
EXAM_THEMES = dict(EXAM_CATEGORIES_CONFIG)
EXAM_THEMES["RECRUITMENT"] = EXAM_CATEGORIES_CONFIG[1]
EXAM_THEMES["APPLICATION"] = EXAM_CATEGORIES_CONFIG[2]
EXAM_THEMES["EXAM_DATE"] = EXAM_CATEGORIES_CONFIG[7]
EXAM_THEMES["ADMIT_CARD"] = EXAM_CATEGORIES_CONFIG[6]
EXAM_THEMES["RESULT"] = EXAM_CATEGORIES_CONFIG[14]
EXAM_THEMES["CORRIGENDUM"] = EXAM_CATEGORIES_CONFIG[20]
for _k, _cfg in EXAM_CATEGORIES_CONFIG.items():
    EXAM_THEMES[_cfg["id"]] = _cfg

def is_valid_stat_metric(val: str) -> bool:
    """Checks whether a vacancy or date metric contains actual data, not boilerplate placeholders."""
    if not val:
        return False
    clean = str(val).strip().lower()
    bad_phrases = [
        "refer to", "refer", "check official", "n/a", "none", "notification pdf",
        "official notice", "official notification", "as per", "to be announced",
        "tba", "not specified", "see notice", "see pdf", "pdf"
    ]
    if any(b in clean for b in bad_phrases):
        return False
    return len(clean) > 0

def detect_exam_scenario(title: str, update_type: str = "") -> dict:
    """
    Classifies notice into one of the 20 approved categories with priority ordering.
    Returns the theme dictionary with category_code embedded.
    """
    combined = f"{title} {update_type}".lower()

    # Priority 1: High-urgency cancellations, changes & special windows
    if any(k in combined for k in ["exam cancelled", "cancelled", "postponed", "deferred"]):
        cat = dict(EXAM_CATEGORIES_CONFIG[9])
        cat["category_code"] = 9
        return cat
    elif any(k in combined for k in ["rescheduled", "revised schedule", "date changed", "exam date revised", "revised exam date"]):
        cat = dict(EXAM_CATEGORIES_CONFIG[8])
        cat["category_code"] = 8
        return cat
    elif any(k in combined for k in ["objection", "key challenge", "inviting objections", "challenge of answer key", "response sheet", "objection management", "objection tracker"]):
        cat = dict(EXAM_CATEGORIES_CONFIG[13])
        cat["category_code"] = 13
        return cat
    elif any(k in combined for k in ["correction window", "edit application", "application correction", "correction in particulars", "edit particulars", "particulars of the online application", "online application correction"]):
        cat = dict(EXAM_CATEGORIES_CONFIG[5])
        cat["category_code"] = 5
        return cat
    elif any(k in combined for k in ["last date extended", "extension of last date", "date extension", "extended up to", "extended to"]):
        cat = dict(EXAM_CATEGORIES_CONFIG[4])
        cat["category_code"] = 4
        return cat

    # Priority 2: Key release & download milestones
    elif any(k in combined for k in ["final answer key", "revised answer key"]):
        cat = dict(EXAM_CATEGORIES_CONFIG[12])
        cat["category_code"] = 12
        return cat
    elif any(k in combined for k in ["answer key", "provisional answer key", "model answer"]):
        cat = dict(EXAM_CATEGORIES_CONFIG[11])
        cat["category_code"] = 11
        return cat
    elif any(k in combined for k in ["city intimation", "centre intimation", "exam city", "examination city", "city allotment", "city slip", "intimation slip"]):
        cat = dict(EXAM_CATEGORIES_CONFIG[10])
        cat["category_code"] = 10
        return cat
    elif any(k in combined for k in ["admit card", "hall ticket", "e-admit", "download admit", "call letter"]):
        cat = dict(EXAM_CATEGORIES_CONFIG[6])
        cat["category_code"] = 6
        return cat
    elif any(k in combined for k in ["document verification", "cv schedule", "counselling", "certificate verification", "dv schedule"]):
        cat = dict(EXAM_CATEGORIES_CONFIG[17])
        cat["category_code"] = 17
        return cat
    elif any(k in combined for k in ["interview date", "viva voce", "skill test", "physical test", "pet/pst", "typing test"]):
        cat = dict(EXAM_CATEGORIES_CONFIG[18])
        cat["category_code"] = 18
        return cat
    elif any(k in combined for k in ["final select", "final merit", "final recommendation", "select list", "final selection list"]):
        cat = dict(EXAM_CATEGORIES_CONFIG[19])
        cat["category_code"] = 19
        return cat

    # Priority 3: Exam outcome & marks declaration
    elif any(k in combined for k in ["declaration of result", "result declared", "cbt result", "written result", "results of", "publication of written test result", "result released"]) or ("result" in combined and not any(k in combined for k in ["cut off", "cutoff"])):
        cat = dict(EXAM_CATEGORIES_CONFIG[14])
        cat["category_code"] = 14
        return cat
    elif any(k in combined for k in ["cut off", "cutoff", "merit list", "shortlisted candidates"]):
        cat = dict(EXAM_CATEGORIES_CONFIG[15])
        cat["category_code"] = 15
        return cat
    elif any(k in combined for k in ["scorecard", "marks secured", "score card"]):
        cat = dict(EXAM_CATEGORIES_CONFIG[16])
        cat["category_code"] = 16
        return cat

    # Priority 4: Dates, Corrigendum & Application cycle
    elif any(k in combined for k in ["corrigendum", "addendum", "modification in", "amendment", "candidature notice"]):
        cat = dict(EXAM_CATEGORIES_CONFIG[20])
        cat["category_code"] = 20
        return cat
    elif any(k in combined for k in ["programme of examination", "schedule of examination", "programme of exam", "schedule of exam", "exam date", "tentative exam date", "examination date"]):
        cat = dict(EXAM_CATEGORIES_CONFIG[7])
        cat["category_code"] = 7
        return cat
    elif any(k in combined for k in ["last date is tomorrow", "closing date is tomorrow", "reminder: last date", "closing soon"]) or (any(k in combined for k in ["last date", "closing date", "deadline"]) and not any(k in combined for k in ["advertisement", "advt", "detailed notification", "applications are invited"])):
        cat = dict(EXAM_CATEGORIES_CONFIG[3])
        cat["category_code"] = 3
        return cat
    elif any(k in combined for k in ["advertisement no", "advt. no", "advt no", "detailed advertisement", "notification no", "recruitment to the post", "detailed notification", "recruitment examination"]):
        cat = dict(EXAM_CATEGORIES_CONFIG[1])
        cat["category_code"] = 1
        return cat
    elif any(k in combined for k in ["apply online from today", "application form link is now active", "registration start", "application start", "application window:"]):
        cat = dict(EXAM_CATEGORIES_CONFIG[2])
        cat["category_code"] = 2
        return cat
    elif any(k in combined for k in ["advertisement", "advt", "applications are invited", "apply online", "recruitment"]):
        cat = dict(EXAM_CATEGORIES_CONFIG[1])
        cat["category_code"] = 1
        return cat

    cat = dict(EXAM_CATEGORIES_CONFIG[20])
    cat["category_code"] = 20
    return cat

def extract_short_board_name(name: str) -> str:
    """
    Extracts a concise, clean short board acronym/name for top-bar badge display.
    Prevents long legal names from colliding with the category badge in the top bar.
    """
    if not name:
        return "EXAM BOARD"
    name = str(name).strip()
    name_upper = name.upper()

    # Priority 1: Check parenthetical acronyms (e.g. "STATE SELECTION BOARD (SSB) ODISHA" -> "SSB ODISHA")
    match = re.search(r'\(([^)]+)\)', name)
    if match:
        acronym = match.group(1).strip().upper()
        if 2 <= len(acronym) <= 10:
            if acronym in ["OPSC", "OSSC", "OSSSC", "OAVS", "OPTCL", "OPGC", "OHPC", "SSC", "UPSC", "RRB", "IBPS", "NTA", "SBI", "RBI"]:
                return acronym
            if "ISRO" in name_upper and "ISRO" not in acronym:
                return f"ISRO {acronym}"
            if "ODISHA" in name_upper and "ODISHA" not in acronym and not acronym.startswith("O"):
                return f"{acronym} ODISHA"
            return acronym

    # Priority 2: Known authoritative short identities
    known_boards = [
        "OSSSC", "OSSC", "OPSC", "SSB ODISHA", "BSE ODISHA", "OAVS", "DSE ODISHA",
        "ODISHA POLICE", "ODISHA HIGH COURT", "DISTRICT COURTS ODISHA", "DISTRICT COURTS",
        "OPTCL", "OMC", "OPGC", "OHPC", "GRIDCO", "SCERT ODISHA", "ODISHA PRISONS",
        "ODISHA FIRE SERVICE", "OFDC", "OSCB",
        "UPSC", "SSC", "RRB", "IBPS", "SBI", "RBI", "NTA", "INDIA POST",
        "INTELLIGENCE BUREAU", "CTET", "KVS", "NVS", "EMRS", "NABARD", "SEBI", "SIDBI",
        "FCI", "LIC", "NIACL", "DRDO", "ISRO", "BARC", "CAPF", "INDIAN COAST GUARD",
        "INDIAN ARMY", "INDIAN NAVY", "INDIAN AIR FORCE", "EPFO", "ESIC", "AAI", "ASRB", "AIIMS",
        "NIELIT", "CSIR"
    ]
    for kb in known_boards:
        if re.search(r'\b' + re.escape(kb) + r'\b', name_upper):
            return kb

    if len(name_upper) > 22:
        return name_upper[:20].strip() + "…"
    return name_upper

def render_exam_alert_card(article_data: dict, output_path: str = None) -> str:
    """
    Renders an authoritative 1080x1080 PNG visual card for an Official Exam Notification.
    Returns the path to the saved PNG image.
    """
    if not output_path:
        output_path = os.path.join(OUTPUT_DIR, "exam_update_slide.png")

    title = str(article_data.get("title", "Official Exam Notification")).strip()
    org_name = str(article_data.get("organization") or article_data.get("exam_board") or "Official Authority").strip()
    board_short = extract_short_board_name(org_name)
    exam_name = str(article_data.get("exam") or article_data.get("target_exam") or org_name).strip()
    vacancies = str(article_data.get("vacancies", "")).strip()
    eligibility = str(article_data.get("eligibility", "")).strip()
    dates = str(article_data.get("dates", "")).strip()
    exam_schedule = str(article_data.get("exam_schedule", "")).strip()
    official_link = str(article_data.get("official_link") or article_data.get("official_source") or "Official Portal").strip()
    bullets = article_data.get("bullets", [])

    # Scenario Detection & Theme Selection (Full 20-Category Support)
    category_input = article_data.get("category_code") or article_data.get("category")
    if category_input and category_input in EXAM_CATEGORIES_CONFIG:
        theme = dict(EXAM_CATEGORIES_CONFIG[category_input])
    elif category_input and str(category_input) in EXAM_THEMES:
        theme = dict(EXAM_THEMES[str(category_input)])
    else:
        theme = detect_exam_scenario(title, article_data.get("update_type", ""))

    # Save resolved theme into article_data for downstream consumers (e.g. Telegram broadcast)
    article_data["category_code"] = theme.get("category_code", 20)
    article_data["category_badge"] = theme.get("badge_text", "📢 OFFICIAL EXAM NOTIFICATION")

    # Adaptive Typography (scaled for 1080x1080 canvas)
    if len(title) > 95:
        headline_size = "34px"
        headline_line_height = "1.24"
    elif len(title) > 65:
        headline_size = "38px"
        headline_line_height = "1.24"
    else:
        headline_size = "42px"
        headline_line_height = "1.22"

    # Extract official domain host cleanly
    try:
        if official_link.startswith("http"):
            domain = urllib.parse.urlparse(official_link).netloc.replace("www.", "")
        else:
            domain = official_link
    except Exception:
        domain = "Official Portal"

    # Format date label (prefer notice date if available, otherwise current date)
    notice_date_raw = article_data.get("notice_date") or article_data.get("published_date")
    if notice_date_raw:
        try:
            today_label = datetime.fromisoformat(str(notice_date_raw)).strftime("%d %B %Y")
        except Exception:
            today_label = str(notice_date_raw)
    else:
        today_label = datetime.now().strftime("%d %B %Y")

    # Build Stat Pills Grid based on available metrics (100% boilerplate-free)
    stat_pills_html = []
    if is_valid_stat_metric(vacancies):
        stat_pills_html.append(f"""
        <div class="stat-pill">
            <span class="stat-icon">👥</span>
            <div class="stat-text">
                <div class="stat-label">TOTAL VACANCIES</div>
                <div class="stat-val">{vacancies}</div>
            </div>
        </div>
        """)
    
    if is_valid_stat_metric(dates):
        stat_pills_html.append(f"""
        <div class="stat-pill">
            <span class="stat-icon">📅</span>
            <div class="stat-text">
                <div class="stat-label">SCHEDULE / DATES</div>
                <div class="stat-val">{dates}</div>
            </div>
        </div>
        """)
    elif is_valid_stat_metric(exam_schedule):
        stat_pills_html.append(f"""
        <div class="stat-pill">
            <span class="stat-icon">⏳</span>
            <div class="stat-text">
                <div class="stat-label">EXAM SCHEDULE</div>
                <div class="stat-val">{exam_schedule}</div>
            </div>
        </div>
        """)

    if len(stat_pills_html) < 2 and is_valid_stat_metric(eligibility):
        clean_elig = eligibility[:45] + ("..." if len(eligibility) > 45 else "")
        stat_pills_html.append(f"""
        <div class="stat-pill">
            <span class="stat-icon">🎓</span>
            <div class="stat-text">
                <div class="stat-label">ELIGIBILITY</div>
                <div class="stat-val">{clean_elig}</div>
            </div>
        </div>
        """)

    # Adaptive fallbacks if fewer than 2 pills to ensure 2 balanced cards with NO empty voids
    if len(stat_pills_html) < 2:
        stat_pills_html.append(f"""
        <div class="stat-pill">
            <span class="stat-icon">🏛️</span>
            <div class="stat-text">
                <div class="stat-label">RECRUITMENT BODY</div>
                <div class="stat-val">{board_short}</div>
            </div>
        </div>
        """)

    if len(stat_pills_html) < 2:
        cat_display = theme.get("name", "Official Update")
        if len(cat_display) > 30:
            cat_display = cat_display[:28] + "…"
        stat_pills_html.append(f"""
        <div class="stat-pill">
            <span class="stat-icon">{theme.get("bullet_icon", "📌")}</span>
            <div class="stat-text">
                <div class="stat-label">UPDATE TYPE</div>
                <div class="stat-val">{cat_display}</div>
            </div>
        </div>
        """)

    stat_grid_block = f'<div class="stat-grid">{"".join(stat_pills_html[:2])}</div>'

    # Build Bullet Cards List (up to 3 concise, high-impact glass cards)
    bullet_cards_html = []
    for b in bullets[:3]:
        clean_b = str(b).strip().replace("**", "").replace("*", "")
        if ":" in clean_b:
            parts = clean_b.split(":", 1)
            tag = parts[0].strip()
            body = parts[1].strip()
            bullet_cards_html.append(f"""
            <div class="bullet-card">
              <div class="bullet-card-content">
                <span class="bullet-badge">{theme['bullet_icon']} {tag}</span>
                <span class="bullet-body">{body}</span>
              </div>
            </div>
            """)
        else:
            bullet_cards_html.append(f"""
            <div class="bullet-card">
              <div class="bullet-card-content">
                <span class="bullet-badge">{theme['bullet_icon']} KEY HIGHLIGHT</span>
                <span class="bullet-body">{clean_b}</span>
              </div>
            </div>
            """)

    if not bullet_cards_html:
        bullet_cards_html.append(f"""
        <div class="bullet-card">
          <div class="bullet-card-content">
            <span class="bullet-badge">{theme['bullet_icon']} OFFICIAL NOTICE</span>
            <span class="bullet-body">Official notification and detailed examination schedule released.</span>
          </div>
        </div>
        """)
        bullet_cards_html.append(f"""
        <div class="bullet-card">
          <div class="bullet-card-content">
            <span class="bullet-badge">{theme['bullet_icon']} CANDIDATE GUIDELINES</span>
            <span class="bullet-body">Candidates can verify eligibility, syllabus, and online application guidelines.</span>
          </div>
        </div>
        """)

    bullets_block = "\n".join(bullet_cards_html)

    # Full Standalone 1080x1080 HTML Template
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800;900&family=Outfit:wght@700;800;900&display=swap" rel="stylesheet">
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      width: 1080px;
      height: 1080px;
      background: {theme["bg_color"]};
      background-image: 
        radial-gradient(at 0% 0%, {theme["radial_1"]} 0px, transparent 55%),
        radial-gradient(at 100% 100%, {theme["radial_2"]} 0px, transparent 55%),
        radial-gradient(at 50% 50%, rgba(15, 23, 42, 0.65) 0px, transparent 80%);
      color: #FFF5F5;
      font-family: 'Plus Jakarta Sans', sans-serif;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      padding: 44px 48px;
      overflow: hidden;
      position: relative;
    }}

    /* Ambient geometric dot matrix */
    body::before {{
      content: '';
      position: absolute;
      inset: 0;
      background-image: radial-gradient(rgba(255, 255, 255, 0.08) 1.2px, transparent 1.2px);
      background-size: 32px 32px;
      pointer-events: none;
      z-index: 1;
    }}

    .top-bar {{
      display: grid;
      grid-template-columns: auto 1fr auto;
      align-items: center;
      width: 100%;
      z-index: 10;
      gap: 16px;
    }}

    .category-badge {{
      background: {theme["badge_gradient"]};
      color: #FFFFFF;
      padding: 11px 22px;
      border-radius: 12px;
      font-weight: 900;
      font-size: 16px;
      letter-spacing: 0.6px;
      text-transform: uppercase;
      box-shadow: 0 4px 20px {theme["glow_color"]};
      display: flex;
      align-items: center;
      gap: 8px;
      border: 1px solid rgba(255, 255, 255, 0.35);
      white-space: nowrap;
      justify-self: start;
    }}

    .board-tag-wrapper {{
      display: flex;
      justify-content: center;
      align-items: center;
      min-width: 0;
      width: 100%;
    }}

    .board-tag {{
      background: rgba(255, 255, 255, 0.15);
      backdrop-filter: blur(16px);
      border: 1.5px solid rgba(255, 255, 255, 0.32);
      color: #FFFFFF;
      padding: 10px 22px;
      border-radius: 12px;
      font-weight: 900;
      font-size: 16px;
      letter-spacing: 1px;
      text-transform: uppercase;
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.30);
      display: flex;
      align-items: center;
      justify-content: center;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      max-width: 100%;
      text-align: center;
    }}

    .date-text {{
      background: rgba(255, 255, 255, 0.08);
      backdrop-filter: blur(12px);
      border: 1px solid rgba(255, 255, 255, 0.16);
      padding: 10px 20px;
      border-radius: 12px;
      font-size: 16px;
      color: #E2E8F0;
      font-weight: 800;
      display: flex;
      align-items: center;
      gap: 6px;
      letter-spacing: 0.5px;
      white-space: nowrap;
      justify-self: end;
    }}

    .main-card {{
      background: {theme["card_bg"]};
      border: 2px solid {theme["border_color"]};
      border-radius: 28px;
      padding: 34px 42px;
      flex: 1;
      margin: 18px 0;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      box-shadow: 0 20px 70px -10px {theme["glow_color"]}, inset 0 1px 0 rgba(255, 255, 255, 0.18);
      z-index: 10;
      position: relative;
    }}

    .card-header {{
      margin-bottom: 4px;
    }}

    .exam-board-title {{
      font-size: 19px;
      font-weight: 800;
      color: {theme["accent_color"]};
      text-transform: uppercase;
      letter-spacing: 1.2px;
      margin-bottom: 6px;
      display: flex;
      align-items: center;
      gap: 8px;
    }}

    .headline {{
      font-family: 'Outfit', sans-serif;
      font-size: {headline_size};
      font-weight: 900;
      line-height: {headline_line_height};
      color: #FFFFFF;
      letter-spacing: -0.3px;
    }}

    .stat-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
      margin: 12px 0 10px 0;
    }}

    .stat-pill {{
      background: rgba(255, 255, 255, 0.06);
      border: 1.5px solid rgba(255, 255, 255, 0.14);
      border-radius: 16px;
      padding: 13px 20px;
      display: flex;
      align-items: center;
      gap: 14px;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
    }}

    .stat-icon {{
      font-size: 30px;
      line-height: 1;
    }}

    .stat-text {{
      display: flex;
      flex-direction: column;
      gap: 2px;
    }}

    .stat-label {{
      font-size: 13px;
      font-weight: 800;
      color: {theme["accent_color"]};
      letter-spacing: 1px;
      text-transform: uppercase;
    }}

    .stat-val {{
      font-size: 21px;
      font-weight: 800;
      color: #FFFFFF;
      letter-spacing: 0.2px;
    }}

    .bullets-container {{
      flex: 1;
      display: flex;
      flex-direction: column;
      justify-content: space-evenly;
      gap: 10px;
      margin: 8px 0;
      min-height: 0;
    }}

    .bullet-card {{
      background: rgba(255, 255, 255, 0.04);
      backdrop-filter: blur(12px);
      border: 1px solid rgba(255, 255, 255, 0.10);
      border-left: 5px solid {theme["accent_color"]};
      border-radius: 16px;
      padding: 13px 20px;
      box-shadow: 0 4px 16px rgba(0, 0, 0, 0.20);
    }}

    .bullet-card-content {{
      font-size: 21px;
      line-height: 1.45;
      color: #F8FAFC;
      font-weight: 500;
    }}

    .bullet-badge {{
      display: inline-flex;
      align-items: center;
      background: rgba(255, 255, 255, 0.12);
      color: {theme["accent_color"]};
      border: 1px solid rgba(255, 255, 255, 0.22);
      padding: 3px 10px;
      border-radius: 8px;
      font-size: 14px;
      font-weight: 900;
      letter-spacing: 0.8px;
      text-transform: uppercase;
      margin-right: 10px;
      vertical-align: middle;
      position: relative;
      top: -2px;
    }}

    .bullet-body {{
      color: #F8FAFC;
    }}

    .official-portal-strip {{
      background: rgba(0, 0, 0, 0.55);
      backdrop-filter: blur(14px);
      border: 1.5px solid rgba(255, 255, 255, 0.16);
      border-radius: 16px;
      padding: 13px 22px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-top: 6px;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.35);
    }}

    .portal-label {{
      font-size: 18px;
      font-weight: 700;
      color: #94A3B8;
      display: flex;
      align-items: center;
      gap: 8px;
    }}

    .portal-link {{
      font-size: 20px;
      font-weight: 800;
      color: #38BDF8;
      letter-spacing: 0.6px;
    }}

    .footer {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-top: 1px solid rgba(255, 255, 255, 0.15);
      padding-top: 16px;
      z-index: 10;
    }}

    .footer-left {{
      display: flex;
      align-items: center;
      gap: 12px;
    }}

    .brand-icon-sm {{
      width: 38px;
      height: 38px;
      background: linear-gradient(135deg, #6366F1 0%, #3B82F6 100%);
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 6px 15px -3px rgba(99, 102, 241, 0.5);
    }}

    .brand-icon-sm svg {{
      width: 24px;
      height: 24px;
    }}

    .website-text {{
      font-size: 21px;
      font-weight: 800;
      color: #FFFFFF;
      letter-spacing: 0.5px;
    }}

    .footer-right {{
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 18px;
      font-weight: 700;
      color: #CBD5E1;
      letter-spacing: 0.5px;
    }}

    .verified-pill {{
      background: rgba(16, 185, 129, 0.2);
      border: 1px solid rgba(16, 185, 129, 0.5);
      color: #6EE7B7;
      padding: 5px 14px;
      border-radius: 8px;
      font-size: 15px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
  </style>
</head>
<body>
  <div class="top-bar">
    <div class="category-badge">{theme["badge_text"]}</div>
    <div class="board-tag-wrapper"><div class="board-tag">{board_short}</div></div>
    <div class="date-text">📅 {today_label}</div>
  </div>

  <div class="main-card">
    <div class="card-header">
      <div class="exam-board-title">🏛️ {org_name} • {exam_name}</div>
      <h1 class="headline">{title}</h1>
    </div>

    {stat_grid_block}

    <div class="bullets-container">
      {bullets_block}
    </div>

    <div class="official-portal-strip">
      <div class="portal-label">🌐 Official Notification Source:</div>
      <div class="portal-link">{domain}</div>
    </div>
  </div>

  <div class="footer">
    <div class="footer-left">
      <div class="brand-icon-sm">
        <svg viewBox="0 0 256 256">
          <g transform="translate(36, 44)" stroke="white" stroke-width="20" stroke-linecap="round" stroke-linejoin="round" fill="none">
            <path d="M84 16 C64 8, 24 10, 4 22 L4 142 C24 130, 64 128, 84 136 Z" />
            <path d="M84 16 C104 8, 144 10, 164 22 L164 142 C144 130, 104 128, 84 136 Z" />
            <line x1="84" y1="16" x2="84" y2="136" />
          </g>
        </svg>
      </div>
      <div class="website-text">www.odishaexamprep.in</div>
    </div>
    <div class="footer-right">
      <span class="verified-pill">✓ Official Source Verified</span>
      <span>Official Update 🚀</span>
    </div>
  </div>
</body>
</html>
"""

    temp_html_path = os.path.join(OUTPUT_DIR, "_temp_exam_card.html")
    with open(temp_html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"])
            page = browser.new_page(viewport={"width": 1080, "height": 1080}, device_scale_factor=2)
            page.goto(f"file:///{os.path.abspath(temp_html_path).replace(os.sep, '/')}", wait_until="networkidle")
            page.screenshot(path=output_path, type="png")
            browser.close()
        print(f"✅ [Exam Card Renderer] 1080x1080 Visual Card saved to {output_path}")
        return output_path
    except Exception as e:
        print(f"⚠️ [Exam Card Renderer] Playwright render note: {e}")
        return ""
    finally:
        if os.path.exists(temp_html_path):
            try:
                os.remove(temp_html_path)
            except Exception:
                pass

if __name__ == "__main__":
    sample_article = {
        "organization": "OSSC",
        "exam": "Combined Graduate Level (CGL) 2026",
        "title": "OSSC CGL 2026 Prelims Examination Date & Shift Timings Released",
        "vacancies": "595 Specialist Posts",
        "dates": "Exam Date: 15 Nov 2026",
        "official_source": "https://www.ossc.gov.in",
        "bullets": [
            "Prelims Schedule: The Preliminary Examination will be conducted across 30 district centers in Odisha on 15th November 2026.",
            "Admit Card Release: Hall tickets with assigned examination centers will be available for download starting 5th November 2026.",
            "Reporting Timings: Candidates must report at examination venues 60 minutes prior to shift commencement with valid photo ID."
        ]
    }
    img = render_exam_alert_card(sample_article)
    print(f"Rendered: {img}")
