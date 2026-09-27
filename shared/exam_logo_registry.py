import os
import sys
import re
from typing import Dict, Any
from PIL import Image, ImageDraw, ImageFont, ImageFilter

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# Dual-environment path resolution: local monorepo vs standalone GitHub Actions runner
parent_public = os.path.join(os.path.dirname(PROJECT_ROOT), "public")
if os.path.exists(parent_public):
    COVERS_DIR = os.path.join(parent_public, "blog_covers")
else:
    COVERS_DIR = os.path.join(PROJECT_ROOT, "public", "blog_covers")

os.makedirs(COVERS_DIR, exist_ok=True)

# BOARD BRANDING & COLOR THEMES
BOARD_THEMES = {
    "OPSC": {
        "full_name": "Odisha Public Service Commission",
        "short_name": "OPSC",
        "bg_top": (10, 25, 47),        # #0A192F
        "bg_bottom": (15, 23, 42),     # #0F172A
        "accent": (37, 99, 235),       # #2563EB Brand Blue
        "accent_glow": (59, 130, 246), # #3B82F6
        "badge_bg": (37, 99, 235),
        "badge_text": (255, 255, 255),
        "gold_accent": (245, 158, 11), # #F59E0B
        "icon_symbol": "🏛️"
    },
    "OSSC": {
        "full_name": "Odisha Staff Selection Commission",
        "short_name": "OSSC",
        "bg_top": (15, 23, 42),        # #0F172A
        "bg_bottom": (30, 41, 59),     # #1E293B
        "accent": (59, 130, 246),      # #3B82F6
        "accent_glow": (6, 182, 212),  # #06B6D4
        "badge_bg": (2, 132, 199),     # #0284C7
        "badge_text": (255, 255, 255),
        "gold_accent": (251, 191, 36),
        "icon_symbol": "📋"
    },
    "OSSSC": {
        "full_name": "Odisha Subordinate Staff Selection Commission",
        "short_name": "OSSSC",
        "bg_top": (6, 30, 20),         # #061E14 Deep Emerald
        "bg_bottom": (15, 23, 42),     # #0F172A
        "accent": (16, 185, 129),      # #10B981 Emerald
        "accent_glow": (20, 184, 166), # #14B8A6
        "badge_bg": (5, 150, 105),     # #059669
        "badge_text": (255, 255, 255),
        "gold_accent": (245, 158, 11),
        "icon_symbol": "🎯"
    },
    "ODISHA POLICE": {
        "full_name": "State Police Recruitment Board, Odisha",
        "short_name": "ODISHA POLICE",
        "bg_top": (30, 8, 8),          # #1E0808 Deep Crimson
        "bg_bottom": (15, 23, 42),     # #0F172A
        "accent": (239, 68, 68),       # #EF4444 Red
        "accent_glow": (245, 158, 11),
        "badge_bg": (220, 38, 38),     # #DC2626
        "badge_text": (255, 255, 255),
        "gold_accent": (234, 179, 8),
        "icon_symbol": "🛡️"
    },
    "BSE ODISHA": {
        "full_name": "Board of Secondary Education, Odisha",
        "short_name": "BSE ODISHA",
        "bg_top": (30, 27, 75),        # #1E1B4B Deep Violet
        "bg_bottom": (15, 23, 42),     # #0F172A
        "accent": (139, 92, 246),      # #8B5CF6
        "accent_glow": (244, 63, 94),
        "badge_bg": (124, 58, 237),    # #7C3AED
        "badge_text": (255, 255, 255),
        "gold_accent": (251, 191, 36),
        "icon_symbol": "🎓"
    },
    "SSC": {
        "full_name": "Staff Selection Commission (Govt of India)",
        "short_name": "SSC CENTRAL",
        "bg_top": (11, 15, 25),        # #0B0F19
        "bg_bottom": (30, 41, 59),     # #1E293B
        "accent": (59, 130, 246),      # #3B82F6
        "accent_glow": (99, 102, 241),
        "badge_bg": (79, 70, 229),     # #4F46E5
        "badge_text": (255, 255, 255),
        "gold_accent": (245, 158, 11),
        "icon_symbol": "🇮🇳"
    },
    "UPSC": {
        "full_name": "Union Public Service Commission",
        "short_name": "UPSC",
        "bg_top": (10, 20, 40),
        "bg_bottom": (15, 23, 42),
        "accent": (37, 99, 235),
        "accent_glow": (217, 119, 6),
        "badge_bg": (30, 64, 175),
        "badge_text": (255, 255, 255),
        "gold_accent": (245, 158, 11),
        "icon_symbol": "⚖️"
    },
    "RAILWAY": {
        "full_name": "Railway Recruitment Board (RRB)",
        "short_name": "RRB RAILWAY",
        "bg_top": (15, 23, 42),
        "bg_bottom": (30, 41, 59),
        "accent": (14, 165, 233),      # #0EA5E9
        "accent_glow": (59, 130, 246),
        "badge_bg": (2, 132, 199),
        "badge_text": (255, 255, 255),
        "gold_accent": (245, 158, 11),
        "icon_symbol": "🚆"
    },
    "BANKING": {
        "full_name": "Institute of Banking Personnel Selection (IBPS)",
        "short_name": "IBPS / BANKING",
        "bg_top": (15, 23, 42),
        "bg_bottom": (17, 24, 39),
        "accent": (16, 185, 129),
        "accent_glow": (59, 130, 246),
        "badge_bg": (15, 118, 110),
        "badge_text": (255, 255, 255),
        "gold_accent": (245, 158, 11),
        "icon_symbol": "🏦"
    },
    "HIGH COURT": {
        "full_name": "High Court of Orissa, Cuttack",
        "short_name": "ORISSA HIGH COURT",
        "bg_top": (15, 23, 42),        # #0F172A Deep Midnight Judicial Navy
        "bg_bottom": (10, 15, 30),     # #0A0F1E
        "accent": (217, 119, 6),       # #D97706 Judicial Bronze / Gold
        "accent_glow": (245, 158, 11), # #F59E0B
        "badge_bg": (180, 83, 9),      # #B45309 Rich Gold-Brown
        "badge_text": (255, 255, 255),
        "gold_accent": (251, 191, 36),
        "icon_symbol": "⚖️"
    },
    "GENERAL_STRATEGY": {
        "full_name": "OdishaExamPrep Masterclass & Strategy Guide",
        "short_name": "EXAM PREPARATION & STRATEGY",
        "bg_top": (15, 23, 42),        # #0F172A
        "bg_bottom": (30, 41, 59),     # #1E293B
        "accent": (99, 102, 241),      # #6366F1 Indigo
        "accent_glow": (14, 165, 233), # #0EA5E9
        "badge_bg": (79, 70, 229),     # #4F46E5
        "badge_text": (255, 255, 255),
        "gold_accent": (245, 158, 11),
        "icon_symbol": "💡"
    }
}

DEFAULT_THEME = BOARD_THEMES["GENERAL_STRATEGY"]

def detect_exam_board_key(text: str) -> str:
    lower = str(text or "").lower()
    if "high court" in lower or "orissa high court" in lower or "ohc" in lower or "judiciary" in lower or "court" in lower:
        return "HIGH COURT"
    elif "opsc" in lower or "oas" in lower:
        return "OPSC"
    elif "ossc" in lower and "osssc" not in lower:
        return "OSSC"
    elif "osssc" in lower or "ri amin" in lower or "nursing officer" in lower:
        return "OSSSC"
    elif "police" in lower or "constable" in lower or "sub-inspector" in lower:
        return "ODISHA POLICE"
    elif "bse" in lower or "otet" in lower or "osstet" in lower:
        return "BSE ODISHA"
    elif "upsc" in lower:
        return "UPSC"
    elif "ssc" in lower:
        return "SSC"
    elif "rrb" in lower or "railway" in lower:
        return "RAILWAY"
    elif "ibps" in lower or "sbi" in lower:
        return "BANKING"
    return "GENERAL_STRATEGY"

def detect_update_badge(title: str, update_type: str = "") -> str:
    combined = f"{str(title or '')} {str(update_type or '')}".lower()
    if any(k in combined for k in ["mock test", "test series", "negative marking", "practice set"]):
        return "MOCK TEST MASTERY"
    elif any(k in combined for k in ["admit card", "hall ticket", "call letter"]):
        return "ADMIT CARD RELEASED"
    elif any(k in combined for k in ["exam date", "schedule", "exam time", "timing", "postponed", "rescheduled"]):
        return "EXAM DATE ANNOUNCED"
    elif any(k in combined for k in ["result", "merit list", "cut off", "scorecard", "qualified", "selected"]):
        return "RESULTS & MERIT LIST"
    elif any(k in combined for k in ["answer key", "objection", "response sheet", "key release"]):
        return "ANSWER KEY RELEASED"
    elif any(k in combined for k in ["syllabus", "exam pattern", "marking scheme", "scheme of exam"]):
        return "OFFICIAL SYLLABUS"
    elif any(k in combined for k in ["vacancy", "recruitment", "notification", "apply online", "form fill up", "posts"]):
        return "OFFICIAL RECRUITMENT"
    elif any(k in combined for k in ["speed", "math", "aptitude", "calculation", "arithmetic"]):
        return "QUANTITATIVE APTITUDE"
    elif any(k in combined for k in ["reasoning", "puzzle", "syllogism"]):
        return "LOGICAL REASONING"
    elif any(k in combined for k in ["grammar", "odia", "english", "vocabulary"]):
        return "LANGUAGE & GRAMMAR"
    elif any(k in combined for k in ["memory", "retention", "revision", "recall", "study"]):
        return "STUDY & REVISION GUIDE"
    return "PREPARATION BLUEPRINT"

def get_best_font(size: int, bold: bool = False):
    """Safely loads system or default TrueType font across Windows & Linux runners."""
    candidates = [
        "C:\\Windows\\Fonts\\segoeuib.ttf" if bold else "C:\\Windows\\Fonts\\segoeui.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf" if bold else "C:\\Windows\\Fonts\\arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()

def wrap_text(text: str, font, max_width: int, draw: ImageDraw.ImageDraw) -> list:
    """Wraps text into multiple lines fitting within max_width pixels."""
    words = text.split()
    lines = []
    current_line = []
    
    for word in words:
        test_line = " ".join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        w = bbox[2] - bbox[0]
        if w <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
    if current_line:
        lines.append(" ".join(current_line))
    return lines[:3]  # Max 3 lines for clean visual balance

def generate_exam_vector_banner(
    title: str,
    target_exam: str = "",
    update_type: str = "",
    slug: str = ""
) -> Dict[str, str]:
    """
    Generates a 1200x675 high-resolution executive graphic card with official board branding,
    crisp typography, executive summary, and structured key points.
    Returns dict with image_url, alt_text, and local_path.
    """
    from shared.imagen_generator import generate_blog_imagen_banner
    res = generate_blog_imagen_banner(
        title=title,
        organization=target_exam,
        category=update_type,
        context_summary="",
        slug=slug
    )
    return {
        "image_url": res["image_url"],
        "alt_text": res["alt_text"],
        "local_path": res.get("local_path"),
        "photographer": res.get("photographer", "OdishaExamPrep Executive Graphics Studio")
    }

