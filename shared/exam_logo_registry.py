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
    lower = text.lower()
    if "opsc" in lower or "oas" in lower:
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
    combined = f"{title} {update_type}".lower()
    if any(k in combined for k in ["admit card", "hall ticket", "call letter"]):
        return "ADMIT CARD RELEASED"
    elif any(k in combined for k in ["exam date", "schedule", "exam time", "timing", "postponed", "rescheduled"]):
        return "EXAM DATE ANNOUNCED"
    elif any(k in combined for k in ["result", "merit list", "cut off", "scorecard", "qualified", "selected"]):
        return "RESULTS & MERIT LIST"
    elif any(k in combined for k in ["answer key", "objection", "response sheet", "key release"]):
        return "ANSWER KEY RELEASED"
    elif any(k in combined for k in ["syllabus", "exam pattern", "scheme", "marking"]):
        return "OFFICIAL SYLLABUS"
    elif any(k in combined for k in ["vacancy", "recruitment", "notification", "apply online", "form fill up", "posts"]):
        return "OFFICIAL RECRUITMENT"
    elif any(k in combined for k in ["mock test", "test series", "negative marking", "score"]):
        return "MOCK TEST MASTERY"
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
    Generates a 1200x630px high-resolution vector graphic banner with official board branding,
    procedural grid background, dynamic category badge, and clean typography.
    Returns dict with image_url, alt_text, and local_path.
    """
    board_key = detect_exam_board_key(f"{target_exam} {title}")
    theme = BOARD_THEMES.get(board_key, DEFAULT_THEME)
    badge_label = detect_update_badge(title, update_type)

    width, height = 1200, 630
    img = Image.new("RGBA", (width, height), theme["bg_top"])
    draw = ImageDraw.Draw(img)

    # 1. Procedural Gradient Background
    for y in range(height):
        ratio = y / float(height)
        r = int(theme["bg_top"][0] * (1 - ratio) + theme["bg_bottom"][0] * ratio)
        g = int(theme["bg_top"][1] * (1 - ratio) + theme["bg_bottom"][1] * ratio)
        b = int(theme["bg_top"][2] * (1 - ratio) + theme["bg_bottom"][2] * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b, 255))

    # 2. Ambient Glow Spheres (Top-Left & Bottom-Right)
    glow_overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_overlay)
    
    # Top-Left Accent Glow
    glow_draw.ellipse([-100, -100, 450, 450], fill=(*theme["accent"], 45))
    # Bottom-Right Gold/Accent Glow
    glow_draw.ellipse([width - 450, height - 350, width + 150, height + 150], fill=(*theme["gold_accent"], 25))
    
    glow_overlay = glow_overlay.filter(ImageFilter.GaussianBlur(radius=65))
    img = Image.alpha_composite(img, glow_overlay)
    draw = ImageDraw.Draw(img)

    # 3. Procedural Vector Geometric Grid Lines
    grid_color = (255, 255, 255, 14)
    for x in range(0, width, 60):
        draw.line([(x, 0), (x, height)], fill=grid_color, width=1)
    for y in range(0, height, 60):
        draw.line([(0, y), (width, y)], fill=grid_color, width=1)

    # 4. Rounded Container Card Frame
    card_margin = 32
    card_rect = [card_margin, card_margin, width - card_margin, height - card_margin]
    draw.rounded_rectangle(card_rect, radius=28, fill=(255, 255, 255, 8), outline=(255, 255, 255, 35), width=2)

    # 5. Top Bar: Board Emblem Pill + Update Badge
    font_board = get_best_font(18, bold=True)
    font_badge = get_best_font(14, bold=True)
    font_title = get_best_font(42, bold=True)
    font_sub = get_best_font(20, bold=False)
    font_footer = get_best_font(16, bold=True)

    # Left Board Pill
    board_pill_text = f"🏛️  {theme['short_name']} • {theme['full_name']}"
    draw.rounded_rectangle([60, 60, 60 + 520, 108], radius=14, fill=(0, 0, 0, 120), outline=theme["accent"], width=2)
    draw.text((78, 74), board_pill_text, fill=(255, 255, 255, 240), font=font_board)

    # Right Category Badge
    badge_full_text = f"🚨 {badge_label}"
    badge_w = 320
    draw.rounded_rectangle([width - 60 - badge_w, 60, width - 60, 108], radius=14, fill=theme["badge_bg"], outline=(255, 255, 255, 80), width=1)
    draw.text((width - 60 - badge_w + 24, 76), badge_full_text, fill=(255, 255, 255), font=font_badge)

    # 6. Main Headline (Center Hero)
    clean_title = re.sub(r'\s+', ' ', title).strip()
    headline_lines = wrap_text(clean_title, font_title, width - 180, draw)
    
    y_text = 175
    for line in headline_lines:
        # Subtle Drop Shadow
        draw.text((62, y_text + 2), line, fill=(0, 0, 0, 160), font=font_title)
        draw.text((60, y_text), line, fill=(255, 255, 255, 255), font=font_title)
        y_text += 62

    # 7. Metadata Highlights Pills (Below Title)
    meta_y = max(y_text + 24, 380)
    pills = [
        f"🏢 Board: {theme['short_name']}",
        f"📍 Odisha State Govt",
        f"✓ Official Verification Active"
    ]
    x_pill = 60
    font_pill = get_best_font(15, bold=True)
    for p in pills:
        draw.rounded_rectangle([x_pill, meta_y, x_pill + 240, meta_y + 44], radius=12, fill=(255, 255, 255, 18), outline=(255, 255, 255, 45), width=1)
        draw.text((x_pill + 16, meta_y + 12), p, fill=theme["gold_accent"], font=font_pill)
        x_pill += 260

    # 8. Bottom Footer Status Bar
    footer_y = height - 90
    draw.line([(card_margin + 20, footer_y - 12), (width - card_margin - 20, footer_y - 12)], fill=(255, 255, 255, 25), width=1)

    # Left Footer Branding
    draw.text((60, footer_y + 4), "OdishaExamPrep Official Portal", fill=(255, 255, 255, 240), font=font_footer)
    draw.text((360, footer_y + 4), "•  https://www.odishaexamprep.in", fill=theme["accent_glow"], font=font_sub)

    # Right Verified Seal Badge
    seal_text = "🛡️ 100% Verified Official Notification"
    draw.text((width - 430, footer_y + 4), seal_text, fill=(52, 211, 153), font=font_footer)

    # 9. Save Image File
    safe_slug = re.sub(r'[^a-z0-9]+', '-', (slug or title).lower()).strip('-')[:50]
    filename = f"banner_{board_key.lower().replace(' ', '_')}_{safe_slug}.png"
    file_path = os.path.join(COVERS_DIR, filename)

    img.save(file_path, "PNG", optimize=True)
    print(f"[ExamVectorEngine] ✅ Generated high-res official vector banner for {board_key}: {filename}")

    public_url = f"https://www.odishaexamprep.in/blog_covers/{filename}"
    alt_text = f"{theme['full_name']} ({theme['short_name']}) - {title} Official Notification"

    return {
        "image_url": public_url,
        "alt_text": alt_text,
        "local_path": file_path,
        "photographer": f"OdishaExamPrep Visual Team ({theme['short_name']} Official)"
    }
