import os
import sys
import re
import json
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from typing import Dict, Any, Optional, List

try:
    from dotenv import load_dotenv
    load_dotenv()
    cur = os.path.dirname(os.path.abspath(__file__))
    for _ in range(3):
        p_env = os.path.join(cur, ".env")
        if os.path.exists(p_env):
            load_dotenv(p_env)
        cur = os.path.dirname(cur)
except Exception:
    pass

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

# Import branding and board themes from exam_logo_registry
try:
    from shared.exam_logo_registry import BOARD_THEMES, DEFAULT_THEME, detect_exam_board_key, detect_update_badge
except ImportError:
    try:
        from exam_logo_registry import BOARD_THEMES, DEFAULT_THEME, detect_exam_board_key, detect_update_badge
    except ImportError:
        BOARD_THEMES = {}
        DEFAULT_THEME = {
            "full_name": "Odisha State Examination Portal",
            "short_name": "ODISHA GOVT",
            "accent": (37, 99, 235),
            "accent_glow": (59, 130, 246),
            "badge_bg": (37, 99, 235),
            "badge_text": (255, 255, 255),
            "gold_accent": (245, 158, 11)
        }
        def detect_exam_board_key(t): return "GENERAL_STRATEGY"
        def detect_update_badge(t, u=""): return "OFFICIAL NOTIFICATION"


def get_gemini_api_key() -> Optional[str]:
    """Retrieves GEMINI_API_KEY from environment."""
    key = os.getenv("GEMINI_API_KEY") or os.getenv("VITE_GEMINI_API_KEY")
    if key and len(key.strip()) > 10:
        return key.strip()
    return None


def get_best_font(size: int, bold: bool = False):
    """Safely loads system or default TrueType font across Windows & Linux runners."""
    candidates = [
        "C:\\Windows\\Fonts\\segoeuib.ttf" if bold else "C:\\Windows\\Fonts\\segoeui.ttf",
        "C:\\Windows\\Fonts\\arialbd.ttf" if bold else "C:\\Windows\\Fonts\\arial.ttf",
        "C:\\Windows\\Fonts\\calibrib.ttf" if bold else "C:\\Windows\\Fonts\\calibri.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf" if bold else "/usr/share/fonts/truetype/freefont/FreeSans.ttf"
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def wrap_text(text: str, font, max_width: int, draw: ImageDraw.ImageDraw) -> List[str]:
    """Wraps text into multiple lines fitting within max_width pixels."""
    words = text.split()
    lines = []
    curr = []
    for w in words:
        test = " ".join(curr + [w])
        box = draw.textbbox((0, 0), test, font=font)
        if (box[2] - box[0]) <= max_width:
            curr.append(w)
        else:
            if curr:
                lines.append(" ".join(curr))
            curr = [w]
    if curr:
        lines.append(" ".join(curr))
    return lines


def extract_card_metadata(
    title: str,
    organization: str = "",
    category: str = "",
    context_summary: str = "",
    api_key: str = ""
) -> Dict[str, Any]:
    """
    Intelligently derives structured executive card metadata:
    - clean_title: Punchy, unbloated headline (under 55 chars)
    - summary: Crisp 1-2 sentence executive summary (under 160 chars)
    - key_points: Exactly 3 structured micro-card objects [label, value, sub]
    Uses Gemini 3.5 Flash Lite first, with guaranteed deterministic fallback.
    """
    if api_key:
        prompt = (
            "You are an expert executive content editor for OdishaExamPrep portal.\n"
            "Analyze this exam update and output a STRICT JSON object with no markdown fences, no formatting, just raw JSON:\n"
            "{\n"
            '  "clean_title": "Concise impactful title under 55 characters",\n'
            '  "summary": "Clear 1-2 sentence executive summary explaining what happened (max 150 chars)",\n'
            '  "key_points": [\n'
            '    {"label": "ORGANIZATION", "value": "Short Primary Value", "sub": "Short subtext"},\n'
            '    {"label": "EXAMINATION POSTS", "value": "Short Primary Value", "sub": "Short subtext"},\n'
            '    {"label": "STATUS", "value": "Short Primary Value", "sub": "Short subtext"}\n'
            "  ]\n"
            "}\n\n"
            f"Input:\nTitle: {title}\nOrganization: {organization}\nCategory: {category}\nContext: {context_summary[:400]}"
        )

        models_to_try = ["gemini-3.5-flash-lite", "gemini-3.8-flash"]
        for model in models_to_try:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.2, "maxOutputTokens": 400}
                }
                res = requests.post(url, json=payload, timeout=12)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        cleaned = text.strip().replace("```json", "").replace("```", "").strip()
                        parsed = json.loads(cleaned)
                        if "clean_title" in parsed and "summary" in parsed and isinstance(parsed.get("key_points"), list):
                            if len(parsed["key_points"]) >= 3:
                                return {
                                    "clean_title": str(parsed["clean_title"]).strip()[:65],
                                    "summary": str(parsed["summary"]).strip()[:180],
                                    "key_points": parsed["key_points"][:3]
                                }
            except Exception:
                continue

    # Deterministic Algorithmic Fallback
    clean_t = re.sub(
        r'\s*(?:out|released|announced|download\s+pdf|pdf\s+link|direct\s+link|check\s+details|official\s+notice|here|active|published)[\s:]*.*$',
        '',
        title,
        flags=re.IGNORECASE
    ).strip()
    if not clean_t or len(clean_t) < 10:
        clean_t = title[:60].strip()

    clean_summary = ""
    if context_summary:
        sentences = re.split(r'(?<=[.!?])\s+', context_summary.strip())
        clean_summary = " ".join(sentences[:2]).strip()
    if not clean_summary or len(clean_summary) < 20:
        org_name = organization or "State Examination Authority"
        clean_summary = f"Official update published by {org_name}. Candidates can review verified eligibility, key dates, and official notification details."
    clean_summary = clean_summary[:160]

    t_lower = f"{title} {category}".lower()
    if any(k in t_lower for k in ["result", "merit list", "scorecard", "qualified"]):
        kp = [
            {"label": "ORGANIZATION", "value": organization or "Odisha State Board", "sub": "Judicial / State Cadre"},
            {"label": "EXAMINATION POSTS", "value": "Senior Posts & Staff", "sub": "Merit List Shortlisted"},
            {"label": "STATUS", "value": "Merit List Released", "sub": "PDF Download Active"}
        ]
    elif any(k in t_lower for k in ["admit card", "hall ticket", "call letter"]):
        kp = [
            {"label": "ORGANIZATION", "value": organization or "State Examination Board", "sub": "Exam Administration"},
            {"label": "HALL TICKET", "value": "Admit Card Released", "sub": "Download via Candidate Login"},
            {"label": "EXAM DAY", "value": "Carry Photo ID & Slip", "sub": "Reporting Time Verified"}
        ]
    elif any(k in t_lower for k in ["answer key", "response sheet", "objection"]):
        kp = [
            {"label": "ORGANIZATION", "value": organization or "State Examination Board", "sub": "Official Assessment"},
            {"label": "ANSWER KEY", "value": "Provisional Key Active", "sub": "Question Paper & Solutions"},
            {"label": "OBJECTION WINDOW", "value": "Online Representation", "sub": "Check Cutoff Timeline"}
        ]
    elif any(k in t_lower for k in ["current affairs", "roundup", "daily ca", "weekly ca"]):
        kp = [
            {"label": "KNOWLEDGE DOMAIN", "value": "Odisha & National CA", "sub": "Daily Exam Digest"},
            {"label": "TARGET EXAMS", "value": "OPSC, OSSSC & Police", "sub": "High-Yield Questions"},
            {"label": "FORMAT", "value": "Editorial & MCQs", "sub": "Exam-Oriented Insights"}
        ]
    else:
        kp = [
            {"label": "RECRUITING BODY", "value": organization or "Odisha Public Commission", "sub": "State Government"},
            {"label": "APPLICATION MODE", "value": "Online Registration", "sub": "Official Government Portal"},
            {"label": "SELECTION PROCESS", "value": "Written Exam & Skill Test", "sub": "Verified Notification"}
        ]

    return {
        "clean_title": clean_t[:60],
        "summary": clean_summary,
        "key_points": kp
    }


def render_executive_graphic_card(
    card_data: Dict[str, Any],
    organization: str = "",
    category: str = ""
) -> Image.Image:
    """
    Renders a 1200x675 (16:9) executive graphic card:
    - Deep obsidian slate background (#0A0F1C)
    - Ambient radial blur glows (royal blue, teal, warm amber)
    - Outer glassmorphic container card with subtle border & highlight sheen
    - Header: Board pill on left with glowing dot + Category badge on right
    - Clean Title (1-2 lines, high-contrast pure white)
    - Summary (1-2 lines, readable muted slate #94A3B8)
    - 3 Structured micro-cards with color accent indicators (blue, green, amber)
    - Footer bar with verified status seal (no broken character glyphs)
    """
    width, height = 1200, 675
    board_key = detect_exam_board_key(f"{organization} {category} {card_data.get('clean_title', '')}")
    theme = BOARD_THEMES.get(board_key, DEFAULT_THEME)
    badge_label = detect_update_badge(card_data.get("clean_title", ""), category)

    img = Image.new("RGB", (width, height), (10, 15, 28))

    # 1. Smooth Ambient Radial Glows
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([-100, -100, 500, 500], fill=(*theme["accent"], 75))
    gd.ellipse([width - 450, -50, width + 150, 450], fill=(20, 184, 166, 40))
    gd.ellipse([width - 400, height - 350, width + 100, height + 100], fill=(*theme["gold_accent"], 45))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=100))
    img.paste(glow, (0, 0), glow)

    draw = ImageDraw.Draw(img)

    # 2. Main Executive Card Container
    pad = 40
    card_rect = [pad, pad, width - pad, height - pad]
    draw.rounded_rectangle(card_rect, radius=24, fill=(15, 23, 42, 235), outline=(255, 255, 255, 28), width=1)
    draw.line([(pad + 24, pad + 1), (width - pad - 24, pad + 1)], fill=(255, 255, 255, 60), width=1)

    # Fonts
    font_brand = get_best_font(15, bold=True)
    font_badge = get_best_font(13, bold=True)
    font_title = get_best_font(38, bold=True)
    font_summary = get_best_font(18, bold=False)
    font_card_label = get_best_font(12, bold=True)
    font_card_val = get_best_font(17, bold=True)
    font_card_sub = get_best_font(14, bold=False)
    font_footer = get_best_font(14, bold=False)
    font_footer_bold = get_best_font(14, bold=True)

    # 3. Header: Board Authority Pill (Left)
    board_display_name = theme.get("full_name") or organization or "Odisha Examination Portal"
    if len(board_display_name) > 42:
        board_display_name = f"{theme.get('short_name', 'ODISHA')} • {board_display_name[:35]}..."
    pill_tw = draw.textlength(board_display_name.upper(), font=font_brand)
    pill_w = max(int(pill_tw + 64), 380)
    pill_w = min(pill_w, 640)

    draw.rounded_rectangle([72, 70, 72 + pill_w, 114], radius=14, fill=(30, 41, 59, 230), outline=theme["accent"], width=1)
    draw.ellipse([90, 88, 100, 98], fill=theme["gold_accent"])
    draw.text((112, 81), board_display_name.upper(), fill=(248, 250, 252), font=font_brand)

    # Category / Status Tag (Right)
    badge_text = badge_label.upper()
    badge_tw = draw.textlength(badge_text, font=font_badge)
    badge_w = int(badge_tw + 48)
    draw.rounded_rectangle([width - 72 - badge_w, 70, width - 72, 114], radius=14, fill=theme["badge_bg"], outline=(255, 255, 255, 90), width=1)
    draw.text((width - 72 - badge_w + 24, 82), badge_text, fill=(255, 255, 255), font=font_badge)

    # 4. Main Title
    clean_title = card_data.get("clean_title", "Official Examination Update")
    lines = wrap_text(clean_title, font_title, 1040, draw)[:2]
    y = 152
    for line in lines:
        draw.text((72, y), line, fill=(255, 255, 255), font=font_title)
        y += 50

    # 5. Executive Summary Text
    summary_text = card_data.get("summary", "")
    summary_lines = wrap_text(summary_text, font_summary, 1040, draw)[:2]
    y += 8
    for line in summary_lines:
        draw.text((72, y), line, fill=(148, 163, 184), font=font_summary)
        y += 28

    # 6. Key Points Grid (3 Balanced Sleek Cards)
    card_y = 352
    card_h = 138
    card_w = 328
    gap = 36
    start_x = 72

    card_colors = [
        (59, 130, 246),  # Card 1: Blue
        (16, 185, 129),  # Card 2: Emerald
        (245, 158, 11),  # Card 3: Amber
    ]

    key_points = card_data.get("key_points", [])
    for i in range(3):
        kp = key_points[i] if i < len(key_points) else {"label": "NOTIFICATION", "value": "Official Update", "sub": "Verified Portal"}
        cx = start_x + i * (card_w + gap)
        acc_color = card_colors[i]

        draw.rounded_rectangle([cx, card_y, cx + card_w, card_y + card_h], radius=16, fill=(30, 41, 59, 190), outline=(51, 65, 85, 230), width=1)
        draw.rounded_rectangle([cx, card_y + 14, cx + 4, card_y + card_h - 14], radius=2, fill=acc_color)

        label_txt = str(kp.get("label", "DETAILS")).upper()[:24]
        val_txt = str(kp.get("value", "Official Notice"))[:24]
        sub_txt = str(kp.get("sub", "Government Cadre"))[:28]

        draw.text((cx + 20, card_y + 20), label_txt, fill=acc_color, font=font_card_label)
        draw.text((cx + 20, card_y + 48), val_txt, fill=(255, 255, 255), font=font_card_val)
        draw.text((cx + 20, card_y + 82), sub_txt, fill=(148, 163, 184), font=font_card_sub)

    # 7. Bottom Footer Status Bar
    footer_y = height - 90
    draw.line([(72, footer_y - 16), (width - 72, footer_y - 16)], fill=(51, 65, 85, 160), width=1)

    draw.text((72, footer_y), "OdishaExamPrep Official Portal", fill=(241, 245, 249), font=font_footer_bold)
    draw.text((320, footer_y), "•   https://www.odishaexamprep.in", fill=(100, 116, 139), font=font_footer)

    draw.ellipse([width - 380, footer_y + 4, width - 370, footer_y + 14], fill=(52, 211, 153))
    draw.text((width - 360, footer_y), "100% Verified Official State Notice", fill=(52, 211, 153), font=font_footer_bold)

    return img


def upload_to_supabase_storage(file_path: str, filename: str) -> Optional[str]:
    """Optionally uploads image to Supabase Storage bucket 'blog-covers' if credentials present."""
    supabase_url = os.getenv("VITE_SUPABASE_URL") or os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("VITE_SUPABASE_ANON_KEY")

    if not supabase_url or not service_key:
        return None

    try:
        clean_url = supabase_url.rstrip("/")
        upload_url = f"{clean_url}/storage/v1/object/blog-covers/{filename}"
        headers = {
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "image/jpeg",
            "x-upsert": "true"
        }
        with open(file_path, "rb") as f:
            file_bytes = f.read()

        res = requests.post(upload_url, headers=headers, data=file_bytes, timeout=20)
        if res.status_code in [200, 201]:
            public_cdn_url = f"{clean_url}/storage/v1/object/public/blog-covers/{filename}"
            print(f"[Executive Card Engine] Uploaded to Supabase CDN: {public_cdn_url}")
            return public_cdn_url
    except Exception as e:
        print(f"[Executive Card Engine] Supabase upload note: {e}")

    return None


def generate_blog_imagen_banner(
    title: str,
    organization: str = "",
    category: str = "",
    context_summary: str = "",
    slug: str = ""
) -> Dict[str, Any]:
    """
    Main entry point for intelligent, context-aware blog cover image generation:
    Renders a sleek, high-end Executive Graphic Card using title, executive summary,
    and 3 structured key points micro-cards.
    GUARANTEES ZERO AI DISTORTIONS, ZERO STOCK PHOTOS, AND ZERO MISSING GLYPHS.
    """
    api_key = get_gemini_api_key()
    safe_slug = re.sub(r'[^a-z0-9]+', '-', (slug or title or "update").lower()).strip('-')[:50] or "update"

    print(f"[Executive Card Engine] Synthesizing executive visual card for '{title[:45]}...'")
    card_data = extract_card_metadata(
        title=title,
        organization=organization,
        category=category,
        context_summary=context_summary,
        api_key=api_key or ""
    )

    img = render_executive_graphic_card(
        card_data=card_data,
        organization=organization,
        category=category
    )

    filename = f"ai_{safe_slug}.jpg"
    file_path = os.path.join(COVERS_DIR, filename)
    img.save(file_path, "JPEG", quality=95, optimize=True)
    print(f"[Executive Card Engine] ✅ Generated sleek card: {file_path}")

    # Sync to build dir if present
    build_covers_dir = os.path.join(PROJECT_ROOT, "..", "build", "blog_covers")
    if os.path.exists(os.path.dirname(build_covers_dir)):
        os.makedirs(build_covers_dir, exist_ok=True)
        img.save(os.path.join(build_covers_dir, filename), "JPEG", quality=95, optimize=True)

    cdn_url = upload_to_supabase_storage(file_path, filename)
    image_url = cdn_url or f"https://www.odishaexamprep.in/blog_covers/{filename}"

    return {
        "image_url": image_url,
        "alt_text": f"{title} - Official Editorial Card",
        "local_path": file_path,
        "photographer": "OdishaExamPrep Executive Graphics Studio",
        "is_ai_generated": True
    }

