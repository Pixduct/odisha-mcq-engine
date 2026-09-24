import os
import sys
import re
import json
import requests
import threading
from datetime import datetime
try:
    from flask import Flask, request, jsonify
    app = Flask(__name__)
except ImportError:
    Flask = None
    request = None
    jsonify = None
    app = None

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(SCRIPT_DIR, "templates", "template_alert.html")
OUTPUT_IMAGE_PATH = os.path.join(SCRIPT_DIR, "breaking_alert.png")

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

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN") or os.getenv("GH_PAT") or ""

# Module-level AI model tracking for admin Telegram report
_breaking_ai_model = "nvidia/nemotron-3-super-120b-a12b"
_breaking_ai_fallback = False

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

def clean_utf8_text(text: str) -> str:
    if not text:
        return ""
    text = str(text)
    text = text.replace("&raquo;", "").replace("&laquo;", "").replace("&nbsp;", " ").replace("&amp;", "&")
    text = text.replace("Â»", "").replace("Â«", "").replace("Â", "")
    text = text.replace("\u00c2\u00bb", "").replace("\u00c2\u00ab", "").replace("\u00c2", "")
    text = text.replace("»", "").replace("«", "")
    text = text.replace("â€“", "–").replace("â€”", "—").replace("â€™", "'").replace("â€œ", '"').replace("â€ ", '"')
    return re.sub(r'\s+', ' ', text).strip()

def truncate_word_safe(text: str, max_len: int = 80) -> str:
    text = clean_utf8_text(text)
    if len(text) <= max_len:
        return text
    truncated = text[:max_len]
    if " " in truncated:
        truncated = truncated.rsplit(" ", 1)[0]
    return truncated.rstrip(",.- ") + "..."

def extract_board_info(text_clean: str, portal_hint: str = "") -> tuple:
    """Returns (short_tag, full_name, default_domain)"""
    text_lower = (clean_utf8_text(text_clean) + " " + portal_hint).lower()
    if "opsc" in text_lower:
        return ("OPSC", "Odisha Public Service Commission", "opsc.gov.in")
    elif "ossc" in text_lower:
        return ("OSSC", "Odisha Staff Selection Commission", "ossc.gov.in")
    elif "osssc" in text_lower:
        return ("OSSSC", "Odisha Subordinate Staff Selection Commission", "osssc.gov.in")
    elif "bse odisha" in text_lower or "bseodisha" in text_lower or "osstet" in text_lower or "otet" in text_lower:
        return ("BSE ODISHA", "Board of Secondary Education, Odisha", "bseodisha.ac.in")
    elif "odisha police" in text_lower or "police" in text_lower:
        return ("ODISHA POLICE", "Odisha Police State Selection Board", "odishapolice.gov.in")
    elif "upsc" in text_lower:
        return ("UPSC", "Union Public Service Commission", "upsc.gov.in")
    elif "ssc" in text_lower:
        return ("SSC", "Staff Selection Commission", "ssc.gov.in")
    elif "rrb" in text_lower or "railway" in text_lower:
        return ("RRB", "Railway Recruitment Board", "rrbbbs.gov.in")
    elif "ibps" in text_lower:
        return ("IBPS", "Institute of Banking Personnel Selection", "ibps.in")
    elif "nta" in text_lower:
        return ("NTA", "National Testing Agency", "nta.ac.in")
    elif "sbi" in text_lower:
        return ("SBI", "State Bank of India Recruitment", "sbi.co.in")
    return ("RECRUITMENT BOARD", "Official Recruitment Authority", "gov.in")

def highlight_keypoint_label(text: str) -> str:
    text = text.strip()
    if "<b>" in text and "</b>" in text:
        return text
    if ":" in text:
        parts = text.split(":", 1)
        label = parts[0].strip()
        val = parts[1].strip()
        return f"<b>{label}:</b> {val}"
    return text

def parse_breaking_notice(raw_notice_text: str, link_url: str = "") -> dict:
    print(f"[VERBOSE LOG] Analyzing notice against 20 Exam Categories ({len(raw_notice_text)} chars)...")

    if not DEEPSEEK_API_KEY or len(raw_notice_text.strip()) == 0:
        return fallback_parse_notice(raw_notice_text, link_url)

    categories_prompt_list = "\n".join([f"{num}. {cfg['name']}" for num, cfg in EXAM_CATEGORIES_CONFIG.items()])

    system_prompt = f"""
You are the Official Exam Alert Specialist & Senior Content Specialist for Odisha & Central India Competitive Exams (OPSC, OSSC, OSSSC, BSE Odisha, Odisha Police, SSC, UPSC, RRB, IBPS, NTA, SBI).
Your primary directive is to AUTONOMOUSLY THINK, EVALUATE, and DYNAMICALLY EXTRACT 100% complete, non-truncated exam alert details from official notices.

======================================================================
1. INTELLECTUAL RELEVANCE EVALUATION & 20-CATEGORY GATEKEEPER
======================================================================
Analyze the incoming raw notice text critically:
• APPROVED RECRUITMENT NOTIFICATION CATEGORIES (Accept & Assign category_code 1 to 20):
{categories_prompt_list}

• LOW-YIELD NOISE & UNAUTHORIZED LISTS (REJECT IMMEDIATELY):
  - Rejected candidate applications lists, individual candidature cancellations, fee non-payment lists.
  - Internal administrative tenders, office vehicle auctions, stationery procurement, staff transfers, departmental promotion committee meetings, non-actionable internal circulars.
  - IF REJECTED: Return "status": "REJECT" and provide a clear "reason".

======================================================================
2. RECRUITMENT DOMAIN KNOWLEDGE & UN-TRUNCATED EXAM TITLES
======================================================================
Use your deep knowledge of competitive exam boards to recognize complete exam titles:
• OSSC: Combined Graduate Level (CGL) Recruitment Examination, Combined Higher Secondary Level (CHSL), Combined Technical Services (CTS), Junior Fisheries Technical Assistant, Accountant, Vital Statistics Assistant.
• OPSC: Odisha Civil Services (OCS), Assistant Section Officer (ASO), Odisha Judicial Service (OJS), Assistant Professor, Medical Officer.
• OSSSC: Combined Recruitment Examination (RI, IARI, AMIN, Forest Guard, Forester, Live Stock Inspector), Junior Assistant (JA), Panchayat Executive Officer (PEO), CRE.
• BSE Odisha: OTET (Odisha Teacher Eligibility Test), OSSTET (Odisha Secondary School Teacher Eligibility Test).
• Odisha Police: Sub-Inspector (SI), Sepoy / Constable, Driver Recruitment.
• SSC / Central: SSC CGL, SSC CHSL, SSC MTS, SSC GD Constable, SSC CPO, UPSC CSE, RRB NTPC, RRB Group D, IBPS PO/Clerk.

CRITICAL RULE: NEVER TRUNCATE EXAM TITLES (e.g. NEVER write "Combined Graduate" — ALWAYS write "Combined Graduate Level (CGL) Recruitment 2025").

======================================================================
3. DYNAMIC CONTEXT EXTRACTION & RICH HIGHLIGHT BULLETS
======================================================================
Extract specific details dynamically from the real notice text (do NOT use static placeholders):
- Extract the real Advertisement/Notice Number (e.g. "Advt No. IIE-58/2024/4125/OSSC")
- Extract the real Post Names & Cadres (e.g. "Auditor, Inspector of Supplies, Junior Assistant")
- Extract the real Vacancy Count (e.g. "595 Posts") or "Refer to Official Notification PDF"
- Extract the real Stage & Dates (e.g. "Preliminary Exam: 20-Oct-2026 | Admit Card: 10-Oct-2026")
- Extract 3 to 4 concise, high-value highlight bullets with bold labels (e.g. "<b>Advt No:</b> 4125/OSSC", "<b>Exam Date:</b> 20 October 2026", "<b>Admit Card Download:</b> Active from 10 October 2026", "<b>Official Link:</b> www.ossc.gov.in")
- Ensure 100% complete sentences with ZERO trailing "..."

Return ONLY valid JSON matching this schema:
{{
  "status": "ACCEPT" | "REJECT",
  "reason": "Clear explanation if rejected",
  "category_code": 1 to 20,
  "exam_board_short": "OSSC",
  "exam_board_full": "Odisha Staff Selection Commission",
  "exam_name": "Combined Graduate Level (CGL) Recruitment Examination 2025",
  "headline": "OSSC CGL 2025 Preliminary Exam Schedule Announced",
  "vacancies": "595 Posts" or "Refer to Official Notice",
  "dates": "20 October 2026" or "Check Official Schedule",
  "official_link": "https://...",
  "bullets": [
    "<b>Advt Reference:</b> Notice No. IIE-58/2024/4125/OSSC",
    "<b>Exam Date:</b> 20 October 2026 (Sunday)",
    "<b>Admit Card:</b> Download active from 10 October 2026",
    "<b>Official Portal:</b> www.ossc.gov.in"
  ]
}}
"""

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    endpoint_url = f"{DEEPSEEK_BASE_URL.rstrip('/')}/chat/completions"
    model_name = "nvidia/nemotron-3-super-120b-a12b" if "nvidia" in DEEPSEEK_BASE_URL else "deepseek-chat"

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": f"Official Link Provided: {link_url}\n\nNotice Text:\n{raw_notice_text[:4000]}"}
        ],
        "temperature": 0.1,
        "max_tokens": 1000,
        "response_format": {"type": "json_object"}
    }

    global _breaking_ai_model, _breaking_ai_fallback
    _breaking_ai_model = model_name
    _breaking_ai_fallback = False

    try:
        # TIER 1 (PRIMARY): Google AI Studio Gemini API
        if GEMINI_API_KEY:
            gemini_prompt = f"{system_prompt.strip()}\n\nOfficial Link Provided: {link_url}\n\nNotice Text:\n{raw_notice_text[:4000]}\n\nCRITICAL: Output ONLY valid pure JSON starting with '{{' and ending with '}}'."
            for g_model in ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.6-flash"]:
                try:
                    g_url = f"https://generativelanguage.googleapis.com/v1beta/models/{g_model}:generateContent?key={GEMINI_API_KEY}"
                    g_payload = {
                        "contents": [{"parts": [{"text": gemini_prompt}]}],
                        "generationConfig": {
                            "response_mime_type": "application/json",
                            "temperature": 0.1,
                            "maxOutputTokens": 1500
                        }
                    }
                    g_res = requests.post(g_url, headers={"Content-Type": "application/json"}, json=g_payload, timeout=35)
                    if g_res.ok:
                        g_json = g_res.json()
                        candidates = g_json.get("candidates", [])
                        if candidates:
                            raw_t = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                            if raw_t and raw_t.strip():
                                parsed_data = json.loads(raw_t.strip())
                                if isinstance(parsed_data, dict):
                                    cat_code = parsed_data.get("category_code", 20)
                                    if not isinstance(cat_code, int) or cat_code not in EXAM_CATEGORIES_CONFIG:
                                        parsed_data["category_code"] = 20
                                    if link_url and not parsed_data.get("official_link"):
                                        parsed_data["official_link"] = link_url
                                    _breaking_ai_model = f"Google Gemini ({g_model}) [Primary]"
                                    _breaking_ai_fallback = False
                                    print(f"✅ [BreakingEngine] Google Gemini ({g_model}) parsed notice successfully.")
                                    return parsed_data
                except Exception as g_err:
                    print(f"⚠️ [BreakingEngine] Google Gemini ({g_model}) failed: {g_err}. Falling over...")

        # TIER 2+ (FALLBACK): NVIDIA NIM Models
        try:
            res = requests.post(endpoint_url, headers=headers, json=payload, timeout=20)
            if not res.ok:
                raise RuntimeError(f"HTTP {res.status_code}")
        except Exception:
            _breaking_ai_model = "z-ai/glm-5.3 (Fallback)"
            _breaking_ai_fallback = True
            fallback_key = (
                os.getenv("NVIDIA_NEMOTRON_KEY") or
                DEEPSEEK_API_KEY or
                ""
            ).strip('"')
            fb_headers = {"Authorization": f"Bearer {fallback_key}", "Content-Type": "application/json"}
            fb_payload = {**payload, "model": "z-ai/glm-5.3"}
            fb_url = "https://integrate.api.nvidia.com/v1/chat/completions"
            res = requests.post(fb_url, headers=fb_headers, json=fb_payload, timeout=35)

        if res.ok:
            result = res.json()
            content = result['choices'][0]['message']['content'].strip()
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            parsed_data = json.loads(content)
            if isinstance(parsed_data, dict):
                cat_code = parsed_data.get("category_code", 20)
                if not isinstance(cat_code, int) or cat_code not in EXAM_CATEGORIES_CONFIG:
                    parsed_data["category_code"] = 20
                if link_url and not parsed_data.get("official_link"):
                    parsed_data["official_link"] = link_url
                return parsed_data
    except Exception as e:
        print(f"⚠️ AI Notice Parsing notice: {e}. Running fallback rule classifier.")

    return fallback_parse_notice(raw_notice_text, link_url)

def fallback_parse_notice(text: str, link_url: str = "") -> dict:
    text_clean = text.strip()
    text_lower = text_clean.lower()
    short_board, full_board, default_domain = extract_board_info(text_clean)

    # Keyword rule-based classification into 20 categories
    cat_code = 20 # Default: Important Notice / Official Update
    if any(k in text_lower for k in ["admit card", "hall ticket", "e-admit", "download admit"]):
        cat_code = 6 # Admit Card Released
    elif any(k in text_lower for k in ["exam cancelled", "cancelled", "postponed", "deferred"]):
        cat_code = 9 # Exam Cancelled / Postponed
    elif any(k in text_lower for k in ["rescheduled", "revised schedule", "date changed", "exam date revised"]):
        cat_code = 8 # Exam Date Rescheduled
    elif any(k in text_lower for k in ["exam date", "schedule of examination", "programme of examination", "tentative exam date"]):
        cat_code = 7 # Exam Date Announced
    elif any(k in text_lower for k in ["final select", "final merit", "final recommendation", "select list"]):
        cat_code = 19 # Final Selection List
    elif any(k in text_lower for k in ["cut off", "cutoff", "merit list", "shortlisted candidates"]):
        cat_code = 15 # Cut-off / Merit List
    elif any(k in text_lower for k in ["scorecard", "marks secured", "score card"]):
        cat_code = 16 # Scorecard Released
    elif any(k in text_lower for k in ["result", "results", "cbt result", "written result"]):
        cat_code = 14 # Result Released
    elif any(k in text_lower for k in ["final answer key", "revised answer key"]):
        cat_code = 12 # Answer Key Revised
    elif any(k in text_lower for k in ["answer key", "provisional answer key", "model answer"]):
        cat_code = 11 # Answer Key Released
    elif any(k in text_lower for k in ["objection", "key challenge", "inviting objections"]):
        cat_code = 13 # Objection Window
    elif any(k in text_lower for k in ["document verification", "cv schedule", "counselling", "certificate verification"]):
        cat_code = 17 # Document Verification
    elif any(k in text_lower for k in ["interview date", "viva voce", "skill test", "physical test", "pet/pst"]):
        cat_code = 18 # Interview / Skill Test
    elif any(k in text_lower for k in ["city intimation", "centre intimation", "exam city"]):
        cat_code = 10 # Exam City Intimation
    elif any(k in text_lower for k in ["last date extended", "extension of last date", "date extension"]):
        cat_code = 4 # Last Date Extended
    elif any(k in text_lower for k in ["last date", "closing date", "deadline"]):
        cat_code = 3 # Application Last Date
    elif any(k in text_lower for k in ["correction window", "edit application", "application correction"]):
        cat_code = 5 # Correction Window
    elif any(k in text_lower for k in ["apply online", "application start", "inviting applications", "registration start"]):
        cat_code = 2 # Application Form Start
    elif any(k in text_lower for k in ["advertisement", "notification no", "recruitment to the post", "detailed notification"]):
        cat_code = 1 # Official Notification Released

    # Build clean headline
    headline = f"{short_board} {EXAM_CATEGORIES_CONFIG[cat_code]['name']}"
    for line in text_clean.split("\n")[:5]:
        line_str = clean_utf8_text(line)
        if len(line_str) > 15 and not line_str.startswith("[") and not line_str.startswith("http"):
            headline = f"{short_board} - {truncate_word_safe(line_str, 65)}"
            break

    bullets = [
        f"<b>Notice Category:</b> {EXAM_CATEGORIES_CONFIG[cat_code]['name']}",
        f"<b>Exam Authority:</b> {full_board}",
        f"<b>Official Source:</b> Visit official portal for document PDF"
    ]

    return {
        "status": "ACCEPT",
        "category_code": cat_code,
        "exam_board_short": short_board,
        "exam_board_full": full_board,
        "exam_name": headline,
        "headline": truncate_word_safe(headline, 75),
        "vacancies": "Refer to Official Notice",
        "dates": "Check Official Portal",
        "official_link": link_url or f"https://{default_domain}",
        "bullets": bullets
    }

def render_breaking_alert_png(alert_data: dict) -> str:
    print("[VERBOSE LOG] Rendering 1080x1080 PNG breaking alert graphic card...")
    try:
        from playwright.sync_api import sync_playwright

        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            html_content = f.read()

        cat_code = alert_data.get("category_code", 20)
        theme = EXAM_CATEGORIES_CONFIG.get(cat_code, EXAM_CATEGORIES_CONFIG[20])

        board_short = alert_data.get("exam_board_short") or "EXAM BOARD"
        board_full = alert_data.get("exam_board_full") or "Official Recruitment Authority"
        headline = alert_data.get("headline") or "Official Exam Notification Released"
        date_str = datetime.now().strftime("%d %B %Y")
        bullets = alert_data.get("bullets", [])
        official_link = alert_data.get("official_link") or "https://ossc.gov.in"
        
        # Extract domain from link
        domain_match = re.search(r'https?://([^/]+)', official_link)
        domain_name = domain_match.group(1) if domain_match else "Official Portal"

        bullet_html_list = []
        for b in bullets:
            formatted_bullet = highlight_keypoint_label(clean_utf8_text(b))
            if formatted_bullet:
                bullet_html_list.append(f"<li>{formatted_bullet}</li>")

        news_bullets_html = "\n        ".join(bullet_html_list[:4])

        # Inject 20-category visual theme tokens
        html_content = html_content.replace("{{THEME_BG_COLOR}}", theme["bg_color"])
        html_content = html_content.replace("{{THEME_RADIAL_1}}", theme["radial_1"])
        html_content = html_content.replace("{{THEME_RADIAL_2}}", theme["radial_2"])
        html_content = html_content.replace("{{THEME_BADGE_GRADIENT}}", theme["badge_gradient"])
        html_content = html_content.replace("{{THEME_GLOW_COLOR}}", theme["glow_color"])
        html_content = html_content.replace("{{THEME_CARD_BG}}", theme["card_bg"])
        html_content = html_content.replace("{{THEME_BORDER_COLOR}}", theme["border_color"])
        html_content = html_content.replace("{{THEME_ACCENT_COLOR}}", theme["accent_color"])
        html_content = html_content.replace("{{THEME_BULLET_ICON}}", theme["bullet_icon"])

        # Inject content
        html_content = html_content.replace("{{CATEGORY_BADGE}}", theme["badge_text"])
        html_content = html_content.replace("{{BOARD_NAME_SHORT}}", board_short)
        html_content = html_content.replace("{{EXAM_BOARD_FULL}}", board_full)
        html_content = html_content.replace("{{HEADLINE}}", headline)
        html_content = html_content.replace("{{NEWS_BULLETS}}", news_bullets_html)
        html_content = html_content.replace("{{OFFICIAL_SOURCE_DOMAIN}}", domain_name)
        html_content = html_content.replace("{{DATE}}", date_str)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1080, "height": 1080})
            page.set_content(html_content, wait_until="networkidle")
            page.evaluate("document.fonts.ready")
            page.wait_for_timeout(800)
            page.screenshot(path=OUTPUT_IMAGE_PATH, type="png")
            browser.close()

        print(f"✅ Breaking alert PNG rendered: {OUTPUT_IMAGE_PATH}")
        return OUTPUT_IMAGE_PATH
    except Exception as e:
        print(f"⚠️ Playwright PNG rendering note: {e}")
        return ""

def build_standalone_caption(alert_data: dict) -> str:
    cat_code = alert_data.get("category_code", 20)
    theme = EXAM_CATEGORIES_CONFIG.get(cat_code, EXAM_CATEGORIES_CONFIG[20])

    badge_text = theme["badge_text"]
    headline = clean_utf8_text(alert_data.get("headline", "Official Exam Notification"))
    board_full = clean_utf8_text(alert_data.get("exam_board_full", "Official Recruitment Board"))
    board_short = clean_utf8_text(alert_data.get("exam_board_short", "Official Board"))
    bullets = alert_data.get("bullets", [])
    official_link = alert_data.get("official_link", "https://ossc.gov.in")

    caption_lines = [
        f"🚨 <b>{badge_text}</b>\n",
        f"📌 <b>{headline}</b>\n",
        f"🏛️ <b>Recruitment Authority:</b> {board_full} ({board_short})"
    ]

    vacancies = alert_data.get("vacancies", "")
    dates = alert_data.get("dates", "")

    if vacancies and "refer to" not in str(vacancies).lower() and vacancies != "N/A":
        caption_lines.append(f"👥 <b>Vacancies:</b> {vacancies}")
    if dates and "check official" not in str(dates).lower() and dates != "N/A":
        caption_lines.append(f"📅 <b>Important Schedule:</b> {dates}")

    if bullets:
        caption_lines.append("\n⚡ <b>Key Updates & Details:</b>")
        for b in bullets:
            clean_b = clean_utf8_text(b)
            if clean_b:
                caption_lines.append(f"• {highlight_keypoint_label(clean_b)}")

    caption_lines.append(f"\n🌐 <b>Direct Official Notification Link:</b>\n👉 {official_link}")
    caption_lines.append(f"\n🚀 <b>Practice Odisha State Mock Tests & PYQs:</b>\n👉 https://www.odishaexamprep.in/")

    return "\n".join(caption_lines)

def send_telegram_photo(token: str, chat_id: str, image_path: str, caption: str) -> bool:
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    print(f"[VERBOSE LOG] Sending photo card to Telegram ({chat_id})...")
    try:
        with open(image_path, "rb") as img_file:
            files = {"photo": img_file}
            data = {
                "chat_id": chat_id,
                "caption": caption[:1024],
                "parse_mode": "HTML"
            }
            res = requests.post(url, data=data, files=files, timeout=30)
            if res.ok:
                print(f"✅ Telegram photo sent successfully to {chat_id}!")
                return True
            else:
                print(f"❌ Telegram sendPhoto failed ({res.status_code}): {res.text}")
    except Exception as e:
        print(f"❌ Telegram sendPhoto exception: {e}")
    return False

def send_telegram_text(token: str, chat_id: str, text: str) -> bool:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text[:4096],
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    try:
        res = requests.post(url, json=payload, timeout=20)
        return res.ok
    except Exception as e:
        print(f"❌ Telegram sendMessage exception: {e}")
        return False

def send_admin_dm_report(alert_data: dict, image_path: str, public_status: bool):
    cat_code = alert_data.get("category_code", 20)
    cat_name = EXAM_CATEGORIES_CONFIG.get(cat_code, {}).get("name", "Official Update")
    board = alert_data.get("exam_board_short", "Board")
    headline = alert_data.get("headline", "")
    official_link = alert_data.get("official_link", "")

    ai_mode_str = f"⚠️ FALLBACK — {_breaking_ai_model}" if _breaking_ai_fallback else f"✅ PRIMARY — {_breaking_ai_model}"

    admin_msg = (
        f"🚨 <b>Exam Notification Alert Execution Report</b>\n\n"
        f"🏷️ <b>Category [{cat_code}/20]:</b> {cat_name}\n"
        f"🏛️ <b>Board:</b> {board}\n"
        f"📌 <b>Headline:</b> {headline}\n"
        f"🌐 <b>Official Link:</b> {official_link}\n"
        f"🤖 <b>AI Model:</b> {ai_mode_str}\n"
        f"📢 <b>Public Channel Broadcast:</b> {'✅ SENT' if public_status else '❌ FAILED'}\n"
        f"✅ <b>Status:</b> SUCCESS"
    )

    if image_path and os.path.exists(image_path):
        send_telegram_photo(TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_CHAT_ID, image_path, admin_msg)
    else:
        send_telegram_text(TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_CHAT_ID, admin_msg)

def process_breaking_notice_direct(raw_text: str, link_url: str = "") -> dict:
    print("==================================================")
    print("🚨 PROCESSING EXAM NOTIFICATION ALERT")
    print("==================================================")

    # Step 1: AI Classification against 20 Categories
    alert_data = parse_breaking_notice(raw_text, link_url)

    if alert_data.get("status") == "REJECT":
        reason = alert_data.get("reason", "Filtered by 20-category gatekeeper (Routine non-exam notice)")
        print(f"ℹ️ Notice REJECTED by 20-Category Gatekeeper: {reason}")
        # Notify Admin DM about skipped notice
        skip_msg = (
            f"ℹ️ <b>Notice Filtered by 20-Category Gatekeeper</b>\n\n"
            f"❓ <b>Reason:</b> {reason}\n"
            f"📝 <b>Raw Notice:</b> {clean_utf8_text(raw_text[:250])}..."
        )
        send_telegram_text(TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_CHAT_ID, skip_msg)
        return alert_data

    # Step 2: Render Category-Specific 1080x1080 PNG Card
    image_path = render_breaking_alert_png(alert_data)

    # Step 3: Format Standalone Telegram Caption (Direct Official URL, Zero Dummy Blog Links)
    caption = build_standalone_caption(alert_data)

    # Step 4: Dispatch to Public Telegram Channel
    public_success = False
    if image_path and os.path.exists(image_path):
        public_success = send_telegram_photo(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, image_path, caption)
    else:
        public_success = send_telegram_text(TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, caption)

    # Step 5: Dispatch Private Admin DM Confirmation Report (with image)
    send_admin_dm_report(alert_data, image_path, public_success)

    return alert_data

if app:
    @app.route("/webhook/breaking-notice", methods=["POST"])
    def webhook_breaking_notice():
        print("\n--------------------------------------------------")
        print("🚨 RECEIVING EXAM NOTIFICATION WEBHOOK")
        print("--------------------------------------------------")

        raw_text = ""
        link_url = ""
        if request.is_json:
            data = request.get_json() or {}
            raw_text = data.get("notice_text") or data.get("notice") or data.get("text") or ""
            link_url = data.get("link") or data.get("url") or ""

        if not raw_text and request.data:
            raw_text = request.data.decode("utf-8", errors="ignore")

        if not raw_text or len(raw_text.strip()) == 0:
            return jsonify({"error": "Empty notice text"}), 400

        try:
            result = process_breaking_notice_direct(raw_text, link_url)
            return jsonify({
                "success": True,
                "category": result.get("category_code"),
                "data": result
            }), 200
        except Exception as e:
            error_msg = f"❌ Error processing breaking notice: {e}"
            print(error_msg)
            send_telegram_text(TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_CHAT_ID, error_msg)
            return jsonify({"error": str(e)}), 500

    @app.route("/trigger/daily-mcq", methods=["GET", "POST"])
    def trigger_daily_mcq():
        try:
            def run_mcq_task():
                import mcq_engine
                mcq_engine.main()

            t = threading.Thread(target=run_mcq_task)
            t.daemon = True
            t.start()
            return jsonify({"success": True, "message": "Daily MCQ Engine triggered"}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/trigger/daily-ca", methods=["GET", "POST"])
    def trigger_daily_ca():
        try:
            def run_ca_task():
                import ca_publisher
                ca_publisher.main()

            t = threading.Thread(target=run_ca_task)
            t.daemon = True
            t.start()
            return jsonify({"success": True, "message": "Daily CA Engine triggered"}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    if app:
        port = int(os.getenv("PORT", 5000))
        print(f"🚀 Starting Exam Notification Alert Engine Flask Server on port {port}...")
        app.run(host="0.0.0.0", port=port, debug=False)
    else:
        print("ℹ️ Flask not installed. Running in standalone library mode.")
