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
    # Strip unrendered template placeholders and JS artifacts
    text = re.sub(r'\[(topic|district|option|exam|insert|placeholder|name)[^\]]*\]', '', text, flags=re.IGNORECASE)
    text = text.replace("[object Object]", "")
    text = re.sub(r'\b(undefined|null)\b', '', text)
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
    """Returns (short_tag, full_name, default_domain) for all Odisha & Central boards."""
    text_lower = (clean_utf8_text(text_clean) + " " + portal_hint).lower()
    
    # 1. Odisha State Authorities
    if "opsc" in text_lower or "odisha public service" in text_lower:
        return ("OPSC", "Odisha Public Service Commission", "opsc.gov.in")
    elif "ossc" in text_lower or "odisha staff selection commission" in text_lower:
        return ("OSSC", "Odisha Staff Selection Commission", "ossc.gov.in")
    elif "osssc" in text_lower or "sub-ordinate staff selection" in text_lower or "subordinate staff" in text_lower:
        return ("OSSSC", "Odisha Subordinate Staff Selection Commission", "osssc.gov.in")
    elif "ssb odisha" in text_lower or "ssbodisha" in text_lower or "state selection board" in text_lower:
        return ("SSB ODISHA", "State Selection Board, Odisha", "ssbodisha.ac.in")
    elif "bse odisha" in text_lower or "bseodisha" in text_lower or "osstet" in text_lower or "otet" in text_lower:
        return ("BSE ODISHA", "Board of Secondary Education, Odisha", "bseodisha.ac.in")
    elif "dse odisha" in text_lower or "dseodisha" in text_lower or "directorate of secondary education" in text_lower or "tgt" in text_lower and "odisha" in text_lower:
        return ("DSE ODISHA", "Directorate of Secondary Education, Odisha", "dseodisha.gov.in")
    elif "odisha police" in text_lower or "police si" in text_lower or "police constable" in text_lower or "sepoy" in text_lower:
        return ("ODISHA POLICE", "Odisha Police State Selection Board", "odishapolice.gov.in")
    elif "oavs" in text_lower or "adarsha vidyalaya" in text_lower:
        return ("OAVS", "Odisha Adarsha Vidyalaya Sangathan", "oav.edu.in")
    elif "high court" in text_lower or "orissa high court" in text_lower:
        return ("ODISHA HIGH COURT", "High Court of Orissa", "orissahighcourt.nic.in")
    elif "district court" in text_lower or "ecourts" in text_lower:
        return ("DISTRICT COURTS", "District Courts of Odisha", "districts.ecourts.gov.in/odisha")
    elif "optcl" in text_lower:
        return ("OPTCL", "Odisha Power Transmission Corporation Limited", "optcl.co.in")
    elif "omc" in text_lower or "odisha mining" in text_lower:
        return ("OMC", "Odisha Mining Corporation", "omcltd.in")
    elif "opgc" in text_lower or "power generation" in text_lower:
        return ("OPGC", "Odisha Power Generation Corporation", "opgc.co.in")
    elif "ohpc" in text_lower or "hydro power" in text_lower:
        return ("OHPC", "Odisha Hydro Power Corporation", "ohpcltd.com")
    elif "gridco" in text_lower:
        return ("GRIDCO", "Grid Corporation of Odisha", "gridco.co.in")
    elif "scert" in text_lower:
        return ("SCERT ODISHA", "State Council of Educational Research & Training, Odisha", "scertodisha.nic.in")
    elif "prisons" in text_lower or "jail warder" in text_lower:
        return ("ODISHA PRISONS", "Directorate of Prisons and Correctional Services, Odisha", "prisons.odisha.gov.in")
    elif "odisha fire" in text_lower or "fire service" in text_lower or "odishafire" in text_lower:
        return ("ODISHA FIRE SERVICE", "Odisha Fire & Emergency Services", "odishafire.gov.in")
    elif "ofdc" in text_lower or "forest development" in text_lower:
        return ("OFDC", "Odisha Forest Development Corporation", "odishafdc.com")
    elif "oscb" in text_lower or "cooperative bank" in text_lower or "rcsodisha" in text_lower:
        return ("OSCB", "Odisha State Cooperative Bank", "rcsodisha.nic.in")
    elif "dtet" in text_lower or "technical education" in text_lower and "odisha" in text_lower:
        return ("DTET ODISHA", "Directorate of Technical Education & Training, Odisha", "dtetodisha.gov.in")
    elif "oscsc" in text_lower or "civil supplies" in text_lower:
        return ("OSCSC", "Odisha State Civil Supplies Corporation", "oscsc.in")
    elif "chse" in text_lower:
        return ("CHSE ODISHA", "Council of Higher Secondary Education, Odisha", "chseodisha.nic.in")

    # 2. Central Government Recruitment Authorities
    elif re.search(r'\bssc\b', text_lower) or "staff selection commission" in text_lower:
        return ("SSC", "Staff Selection Commission", "ssc.gov.in")
    elif re.search(r'\brrb\b', text_lower) or re.search(r'\brrc\b', text_lower) or "railway" in text_lower:
        return ("RRB", "Railway Recruitment Board", "rrbapply.gov.in")
    elif re.search(r'\bupsc\b', text_lower) or "union public service" in text_lower:
        return ("UPSC", "Union Public Service Commission", "upsc.gov.in")
    elif re.search(r'\bibps\b', text_lower) or "banking personnel" in text_lower:
        return ("IBPS", "Institute of Banking Personnel Selection", "ibps.in")
    elif re.search(r'\bsbi\b', text_lower) or "state bank of india" in text_lower:
        return ("SBI", "State Bank of India Recruitment", "sbi.co.in")
    elif re.search(r'\brbi\b', text_lower) or "reserve bank" in text_lower:
        return ("RBI", "Reserve Bank of India", "rbi.org.in")
    elif re.search(r'\bnta\b', text_lower) or "national testing agency" in text_lower:
        return ("NTA", "National Testing Agency", "nta.ac.in")
    elif "india post" in text_lower or re.search(r'\bgds\b', text_lower) or "dak sevak" in text_lower or "indiapost" in text_lower:
        return ("INDIA POST", "Department of Posts, India", "indiapostgdsonline.gov.in")
    elif "intelligence bureau" in text_lower or " ib acio" in text_lower or "mha ib" in text_lower:
        return ("INTELLIGENCE BUREAU", "Intelligence Bureau, Ministry of Home Affairs", "mha.gov.in")
    elif re.search(r'\bctet\b', text_lower) or "central teacher eligibility" in text_lower:
        return ("CTET", "Central Teacher Eligibility Test (CBSE)", "ctet.nic.in")
    elif re.search(r'\bkvs\b', text_lower) or "kendriya vidyalaya" in text_lower:
        return ("KVS", "Kendriya Vidyalaya Sangathan", "kvsangathan.nic.in")
    elif re.search(r'\bnvs\b', text_lower) or "navodaya vidyalaya" in text_lower:
        return ("NVS", "Navodaya Vidyalaya Samiti", "navodaya.gov.in")
    elif re.search(r'\bemrs\b', text_lower) or "eklavya model" in text_lower:
        return ("EMRS", "National Education Society for Tribal Students", "emrs.tribal.gov.in")

    # Science, Space & Defence
    elif re.search(r'\biprc\b', text_lower) or "propulsion complex" in text_lower:
        return ("ISRO IPRC", "ISRO Propulsion Complex (IPRC)", "isro.gov.in")
    elif re.search(r'\blpsc\b', text_lower):
        return ("ISRO LPSC", "Liquid Propulsion Systems Centre (LPSC)", "lpsc.gov.in")
    elif re.search(r'\bvssc\b', text_lower):
        return ("ISRO VSSC", "Vikram Sarabhai Space Centre (VSSC)", "vssc.gov.in")
    elif re.search(r'\bursc\b', text_lower):
        return ("ISRO URSC", "U R Rao Satellite Centre (URSC)", "ursc.gov.in")
    elif re.search(r'\bisro\b', text_lower) or "indian space research" in text_lower:
        return ("ISRO", "Indian Space Research Organisation", "isro.gov.in")
    elif re.search(r'\bdrdo\b', text_lower) or "ceptam" in text_lower:
        return ("DRDO", "Defence Research and Development Organisation", "drdo.gov.in")
    elif re.search(r'\bbarc\b', text_lower) or "bhabha atomic" in text_lower:
        return ("BARC", "Bhabha Atomic Research Centre", "barc.gov.in")
    elif "capf" in text_lower or re.search(r'\bcrpf\b', text_lower) or re.search(r'\bbsf\b', text_lower) or re.search(r'\bcisf\b', text_lower) or re.search(r'\bitbp\b', text_lower) or "ssbrectt" in text_lower or "assam rifles" in text_lower:
        return ("CAPF", "Central Armed Police Forces (MHA)", "mha.gov.in")
    elif "coast guard" in text_lower or "indian coast guard" in text_lower or re.search(r'\bicg\b', text_lower):
        return ("INDIAN COAST GUARD", "Indian Coast Guard (Ministry of Defence)", "joinindiancoastguard.cdac.in")
    elif "indian army" in text_lower or "joinindianarmy" in text_lower or "army agniveer" in text_lower:
        return ("INDIAN ARMY", "Indian Army Recruitment", "joinindianarmy.nic.in")
    elif "indian navy" in text_lower or "joinindiannavy" in text_lower or "navy agniveer" in text_lower:
        return ("INDIAN NAVY", "Indian Navy Recruitment", "joinindiannavy.gov.in")
    elif "air force" in text_lower or "agnipathvayu" in text_lower or "afcat" in text_lower or re.search(r'\biaf\b', text_lower):
        return ("INDIAN AIR FORCE", "Indian Air Force (IAF)", "agnipathvayu.cdac.in")

    # Financial, Insurance & PSUs
    elif "nabard" in text_lower:
        return ("NABARD", "National Bank for Agriculture and Rural Development", "nabard.org")
    elif re.search(r'\bsebi\b', text_lower):
        return ("SEBI", "Securities and Exchange Board of India", "sebi.gov.in")
    elif re.search(r'\bsidbi\b', text_lower):
        return ("SIDBI", "Small Industries Development Bank of India", "sidbi.in")
    elif re.search(r'\bfci\b', text_lower) or "food corporation" in text_lower:
        return ("FCI", "Food Corporation of India", "fci.gov.in")
    elif re.search(r'\blic\b', text_lower) or "life insurance" in text_lower or "licindia" in text_lower:
        return ("LIC", "Life Insurance Corporation of India", "licindia.in")
    elif re.search(r'\bniacl\b', text_lower) or "new india assurance" in text_lower:
        return ("NIACL", "New India Assurance Company Limited", "newindia.co.in")
    elif "epfo" in text_lower or "provident fund" in text_lower:
        return ("EPFO", "Employees' Provident Fund Organisation", "epfindia.gov.in")
    elif "esic" in text_lower or "employees' state insurance" in text_lower:
        return ("ESIC", "Employees' State Insurance Corporation", "esic.gov.in")
    elif "aai" in text_lower or "airports authority" in text_lower:
        return ("AAI", "Airports Authority of India", "aai.aero")
    elif "asrb" in text_lower or "icar" in text_lower:
        return ("ASRB", "Agricultural Scientists Recruitment Board", "asrb.org.in")
    elif "aiims" in text_lower or "norcet" in text_lower:
        return ("AIIMS", "All India Institute of Medical Sciences", "aiimsexams.ac.in")
    elif "nielit" in text_lower or "national institute of electronics" in text_lower:
        return ("NIELIT", "National Institute of Electronics & Information Technology", "nielit.gov.in")
    elif "csir" in text_lower:
        return ("CSIR", "Council of Scientific & Industrial Research", "csir.res.in")

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
1. ZERO-HALLUCINATION GROUNDING & STRICT SOURCE AUTHENTICITY MANDATE
======================================================================
- ZERO TOLERANCE FOR FABRICATED DATA: Every date, vacancy count, and advertisement number MUST be grounded in the official notice text provided.
- UNVERIFIED METRICS: If the vacancy figure is not explicitly detailed in the notice, you MUST output "Refer to Official Notice PDF". NEVER guess, hallucinate, or extrapolate vacancy figures.
- TENTATIVE/UNANNOUNCED DATES: If the exam date or schedule is marked "to be intimated later" or not explicitly stated, you MUST output "To Be Intimated Later" or "Check Official Schedule". NEVER invent dates.
- EXACT ADVT / NOTIFICATION NO: Extract the exact recruitment reference (e.g., "Advt No. IIE-58/2024/4125/OSSC") verbatim.
- PROHIBITION OF GHOST CLAIMS: Never assert syllabus changes or application re-openings unless verbatim in the notice text.

======================================================================
2. INTELLECTUAL RELEVANCE EVALUATION & 20-CATEGORY GATEKEEPER
======================================================================
Analyze the incoming raw notice text critically:
• APPROVED RECRUITMENT NOTIFICATION CATEGORIES (Accept & Assign category_code 1 to 20):
{categories_prompt_list}

• LOW-YIELD NOISE & UNAUTHORIZED LISTS (REJECT IMMEDIATELY):
  - Rejected candidate applications lists, individual candidature cancellations, fee non-payment lists.
  - Internal administrative tenders, office vehicle auctions, stationery procurement, staff transfers, departmental promotion committee meetings, non-actionable internal circulars.
  - IF REJECTED: Return "status": "REJECT" and provide a clear "reason".

======================================================================
3. RECRUITMENT DOMAIN KNOWLEDGE & UN-TRUNCATED EXAM TITLES
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
4. DYNAMIC CONTEXT EXTRACTION & RICH HIGHLIGHT BULLETS
======================================================================
Extract specific details dynamically from the real notice text (do NOT use static placeholders):
- Extract the real Advertisement/Notice Number (e.g. "Advt No. IIE-58/2024/4125/OSSC")
- Extract the real Post Names & Cadres (e.g. "Auditor, Inspector of Supplies, Junior Assistant")
- Extract the real Vacancy Count (e.g. "595 Posts") or "Refer to Official Notice PDF"
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
  "vacancies": "595 Posts" or "Refer to Official Notice PDF",
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
            {"role": "user", "content": f"Official Link Provided: {link_url}\n\nNotice Text:\n{raw_notice_text[:35000]}"}
        ],
        "temperature": 0.1,
        "max_tokens": 3000,
        "response_format": {"type": "json_object"}
    }

    global _breaking_ai_model, _breaking_ai_fallback
    _breaking_ai_model = model_name
    _breaking_ai_fallback = False

    try:
        # TIER 1 (PRIMARY): Google AI Studio Gemini API
        # Always tried first. Retries on 429 (quota) and 503 (high demand) before falling over.
        gemini_last_err = ""
        GEMINI_MODELS = ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.6-flash", "gemini-3.7-flash", "gemini-3.8-flash", "gemini-3.1-flash-lite"]
        if GEMINI_API_KEY:
            gemini_prompt = f"{system_prompt.strip()}\n\nOfficial Link Provided: {link_url}\n\nNotice Text:\n{raw_notice_text[:35000]}\n\nCRITICAL: Output ONLY valid pure JSON starting with '{{' and ending with '}}'."
            for g_model in GEMINI_MODELS:
                if not gemini_last_err.startswith("__success"):
                    max_model_attempts = 2
                    for attempt in range(1, max_model_attempts + 1):
                        try:
                            print(f"🚀 [BreakingEngine] Calling Gemini ({g_model}) attempt {attempt}...")
                            g_url = f"https://generativelanguage.googleapis.com/v1beta/models/{g_model}:generateContent?key={GEMINI_API_KEY}"
                            g_payload = {
                                "contents": [{"parts": [{"text": gemini_prompt}]}],
                                "generationConfig": {
                                    "response_mime_type": "application/json",
                                    "temperature": 0.1,
                                    "maxOutputTokens": 3000
                                }
                            }
                            g_res = requests.post(g_url, headers={"Content-Type": "application/json"}, json=g_payload, timeout=40)
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
                                            print(f"✅ [BreakingEngine] Gemini ({g_model}) parsed notice successfully.")
                                            return parsed_data
                            elif g_res.status_code == 429:
                                gemini_last_err = f"{g_model}: HTTP 429 quota"
                                if attempt < max_model_attempts:
                                    import time as _t
                                    print(f"⏳ [BreakingEngine] Gemini ({g_model}) HTTP 429 — waiting 65s for quota reset...")
                                    _t.sleep(65)
                                    continue
                                else:
                                    print(f"⚠️ [BreakingEngine] Gemini ({g_model}) quota exhausted after retry. Trying next model...")
                            elif g_res.status_code == 503:
                                gemini_last_err = f"{g_model}: HTTP 503 high demand"
                                if attempt < max_model_attempts:
                                    import time as _t
                                    print(f"⏳ [BreakingEngine] Gemini ({g_model}) HTTP 503 — waiting 30s then retrying...")
                                    _t.sleep(30)
                                    continue
                                else:
                                    print(f"⚠️ [BreakingEngine] Gemini ({g_model}) still busy after retry. Trying next model...")
                            else:
                                gemini_last_err = f"{g_model}: HTTP {g_res.status_code} - {g_res.text[:100]}"
                                print(f"⚠️ [BreakingEngine] Gemini ({g_model}) HTTP {g_res.status_code}. Trying next model...")
                            break
                        except Exception as g_err:
                            gemini_last_err = f"{g_model}: {g_err}"
                            print(f"⚠️ [BreakingEngine] Gemini ({g_model}) failed: {g_err}. Trying next model...")
                            break

        if gemini_last_err and not gemini_last_err.startswith("__success"):
            print(f"⚠️ [BreakingEngine] All Gemini models exhausted. Transitioning to NVIDIA NIM as last resort...")


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
                try:
                    from shared.telegram import send_ai_fallback_notification
                    send_ai_fallback_notification(
                        engine="breaking_engine (Exam Notice Alerts)",
                        primary_error=gemini_last_err or "Gemini models exhausted",
                        fallback_model=_breaking_ai_model,
                        context_topic=f"Notice: {raw_notice_text[:100]}"
                    )
                except Exception as alert_err:
                    print(f"⚠️ [Alert Failed]: {alert_err}")
                return parsed_data
    except Exception as e:
        print(f"⚠️ AI Notice Parsing notice: {e}. Running fallback rule classifier.")

    return fallback_parse_notice(raw_notice_text, link_url)

def fallback_parse_notice(text: str, link_url: str = "") -> dict:
    text_clean = text.strip()
    text_lower = text_clean.lower()
    short_board, full_board, default_domain = extract_board_info(text_clean)

    # Keyword rule-based classification into 20 categories (ordered by specificity)
    cat_code = 20 # Default: Important Notice / Official Update

    # Priority 1: High-urgency cancellations, changes & special windows
    if any(k in text_lower for k in ["exam cancelled", "cancelled", "postponed", "deferred"]):
        cat_code = 9 # Exam Cancelled / Postponed
    elif any(k in text_lower for k in ["rescheduled", "revised schedule", "date changed", "exam date revised", "revised exam date"]):
        cat_code = 8 # Exam Date Rescheduled
    elif any(k in text_lower for k in ["objection", "key challenge", "inviting objections", "challenge of answer key"]):
        cat_code = 13 # Objection Window
    elif any(k in text_lower for k in ["correction window", "edit application", "application correction", "correction in particulars", "edit particulars"]):
        cat_code = 5 # Correction Window
    elif any(k in text_lower for k in ["last date extended", "extension of last date", "date extension", "extended up to", "extended to"]):
        cat_code = 4 # Last Date Extended

    # Priority 2: Key release & download milestones
    elif any(k in text_lower for k in ["final answer key", "revised answer key"]):
        cat_code = 12 # Answer Key Revised
    elif any(k in text_lower for k in ["answer key", "provisional answer key", "model answer"]):
        cat_code = 11 # Answer Key Released
    elif any(k in text_lower for k in ["city intimation", "centre intimation", "exam city", "examination city", "city allotment", "city slip", "intimation slip"]):
        cat_code = 10 # Exam City Intimation
    elif any(k in text_lower for k in ["admit card", "hall ticket", "e-admit", "download admit", "call letter"]):
        cat_code = 6 # Admit Card Released
    elif any(k in text_lower for k in ["document verification", "cv schedule", "counselling", "certificate verification", "dv schedule"]):
        cat_code = 17 # Document Verification
    elif any(k in text_lower for k in ["interview date", "viva voce", "skill test", "physical test", "pet/pst", "typing test"]):
        cat_code = 18 # Interview / Skill Test
    elif any(k in text_lower for k in ["final select", "final merit", "final recommendation", "select list", "final selection list"]):
        cat_code = 19 # Final Selection List

    # Priority 3: Exam outcome & marks declaration
    elif any(k in text_lower for k in ["declaration of result", "result declared", "cbt result", "written result", "results of", "publication of written test result", "result released"]) or ("result" in text_lower and not any(k in text_lower for k in ["cut off", "cutoff"])):
        cat_code = 14 # Result Released
    elif any(k in text_lower for k in ["cut off", "cutoff", "merit list", "shortlisted candidates"]):
        cat_code = 15 # Cut-off / Merit List
    elif any(k in text_lower for k in ["scorecard", "marks secured", "score card"]):
        cat_code = 16 # Scorecard Released

    # Priority 4: Dates, Corrigendum & Application cycle
    elif any(k in text_lower for k in ["corrigendum", "addendum", "modification in", "amendment", "candidature notice"]):
        cat_code = 20 # Important Official Notice
    elif any(k in text_lower for k in ["programme of examination", "schedule of examination", "programme of exam", "schedule of exam", "exam date", "tentative exam date", "examination date"]):
        cat_code = 7 # Exam Date Announced
    elif any(k in text_lower for k in ["last date is tomorrow", "closing date is tomorrow", "reminder: last date", "closing soon"]) or (any(k in text_lower for k in ["last date", "closing date", "deadline"]) and not any(k in text_lower for k in ["advertisement", "advt", "detailed notification", "applications are invited"])):
        cat_code = 3 # Application Last Date
    elif any(k in text_lower for k in ["advertisement no", "advt. no", "advt no", "detailed advertisement", "notification no", "recruitment to the post", "detailed notification", "recruitment examination"]):
        cat_code = 1 # Official Notification Released
    elif any(k in text_lower for k in ["apply online from today", "application form link is now active", "registration start", "application start", "application window:"]):
        cat_code = 2 # Application Form Start
    elif any(k in text_lower for k in ["advertisement", "advt", "applications are invited", "apply online", "recruitment"]):
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
        "vacancies": "",
        "dates": "",
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

        raw_board = alert_data.get("exam_board_short") or alert_data.get("exam_board_full") or "EXAM BOARD"
        try:
            from exam_card_renderer import extract_short_board_name
            board_short = extract_short_board_name(raw_board)
        except Exception:
            board_short = str(raw_board).strip()
            if len(board_short) > 22:
                board_short = board_short[:20] + "…"
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
            cleaned_b = clean_utf8_text(b).strip()
            if not cleaned_b:
                continue
            lbl = ""
            body = cleaned_b
            if "<b>" in cleaned_b and "</b>" in cleaned_b:
                m = re.match(r'<b>([^<:]+):?</b>\s*(.*)', cleaned_b)
                if m:
                    lbl = m.group(1).strip()
                    body = m.group(2).strip()
            elif ":" in cleaned_b:
                parts = cleaned_b.split(":", 1)
                lbl = parts[0].strip()
                body = parts[1].strip()

            if lbl:
                bullet_html_list.append(
                    f'<div class="bullet-card"><div class="bullet-card-content">'
                    f'<span class="bullet-badge">{lbl}</span>'
                    f'<span class="bullet-body">{body}</span>'
                    f'</div></div>'
                )
            else:
                bullet_html_list.append(
                    f'<div class="bullet-card"><div class="bullet-card-content">'
                    f'<span class="bullet-body">{body}</span>'
                    f'</div></div>'
                )

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

    try:
        from shared.telegram import is_valid_metric
    except ImportError:
        def is_valid_metric(val):
            return bool(val and str(val).strip().lower() not in ["n/a", "none", "", "refer to notice"])

    if board_short and board_short.lower() not in board_full.lower():
        board_display = f"{board_full} ({board_short})"
    else:
        board_display = board_full

    caption_lines = [
        f"🚨 <b>{badge_text}</b>\n",
        f"📌 <b>{headline}</b>\n",
        f"🏛️ <b>Recruitment Authority:</b> {board_display}"
    ]

    vacancies = alert_data.get("vacancies", "")
    dates = alert_data.get("dates", "")

    if is_valid_metric(vacancies):
        caption_lines.append(f"👥 <b>Vacancies:</b> {vacancies}")
    if is_valid_metric(dates):
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
