import os
import sys
import re
from datetime import datetime
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = SCRIPT_DIR

# Future-Proof Dynamic Color Palettes (Clean Pill Badges - No Emojis)
DYNAMIC_COLOR_PALETTES = [
    # 0: Crimson Red (Exams / Notices / Breaking)
    {"primary": "#EF4444", "badge_bg": "linear-gradient(135deg, #EF4444 0%, #B91C1C 100%)", "border": "rgba(239, 68, 68, 0.45)", "glow": "rgba(239, 68, 68, 0.35)", "accent": "#FCA5A5"},
    # 1: Royal Indigo (Schemes & Policies)
    {"primary": "#6366F1", "badge_bg": "linear-gradient(135deg, #6366F1 0%, #4338CA 100%)", "border": "rgba(99, 102, 241, 0.45)", "glow": "rgba(99, 102, 241, 0.35)", "accent": "#A5B4FC"},
    # 2: Emerald Green (Appointments & Honours)
    {"primary": "#10B981", "badge_bg": "linear-gradient(135deg, #10B981 0%, #047857 100%)", "border": "rgba(16, 185, 129, 0.45)", "glow": "rgba(16, 185, 129, 0.35)", "accent": "#6EE7B7"},
    # 3: Cyan Blue (Economy & Tech)
    {"primary": "#06B6D4", "badge_bg": "linear-gradient(135deg, #06B6D4 0%, #3B82F6 100%)", "border": "rgba(6, 182, 212, 0.45)", "glow": "rgba(6, 182, 212, 0.35)", "accent": "#38BDF8"},
    # 4: Amber Gold (Sports & Games)
    {"primary": "#F59E0B", "badge_bg": "linear-gradient(135deg, #F59E0B 0%, #B45309 100%)", "border": "rgba(245, 158, 11, 0.45)", "glow": "rgba(245, 158, 11, 0.35)", "accent": "#FDE047"},
    # 5: Electric Purple (Science & Space / Tech)
    {"primary": "#8B5CF6", "badge_bg": "linear-gradient(135deg, #8B5CF6 0%, #6D28D9 100%)", "border": "rgba(139, 92, 246, 0.45)", "glow": "rgba(139, 92, 246, 0.35)", "accent": "#C4B5FD"},
    # 6: Deep Orange (Defence & Security)
    {"primary": "#EA580C", "badge_bg": "linear-gradient(135deg, #EA580C 0%, #9A3412 100%)", "border": "rgba(234, 88, 12, 0.45)", "glow": "rgba(234, 88, 12, 0.35)", "accent": "#FDBA74"},
    # 7: Mint Teal (Environment & Ecology)
    {"primary": "#14B8A6", "badge_bg": "linear-gradient(135deg, #14B8A6 0%, #0F766E 100%)", "border": "rgba(20, 184, 166, 0.45)", "glow": "rgba(20, 184, 166, 0.35)", "accent": "#5EEAD4"},
    # 8: Sapphire Blue (International / World News)
    {"primary": "#2563EB", "badge_bg": "linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%)", "border": "rgba(37, 99, 235, 0.45)", "glow": "rgba(37, 99, 235, 0.35)", "accent": "#93C5FD"}
]

KEYWORD_COLOR_MAP = {
    "EXAM": 0, "NOTICE": 0, "NOTIFICATION": 0, "BREAKING": 0, "RECRUITMENT": 0,
    "OPSC": 0, "OSSC": 0, "OSSSC": 0, "OPPRB": 0, "SSB": 0, "BSE": 0, "CHSE": 0, "OJEE": 0,
    "SSC": 0, "UPSC": 0, "NTA": 0, "IBPS": 0, "SBI": 0, "RRB": 0, "RRC": 0, "GATE": 0, "NET": 0,
    "CTET": 0, "OTET": 0, "OSSTET": 0, "KVS": 0, "NVS": 0, "ADMIT": 0, "RESULT": 0, "VACANCY": 0,
    "SYLLABUS": 0, "HALL TICKET": 0, "CUT OFF": 0,
    "SCHEME": 1, "POLICY": 1, "YOJANA": 1, "CABINET": 1, "GOVT": 1, "GOVERNMENT": 1,
    "APPOINTMENT": 2, "HONOUR": 2, "HONOR": 2, "AWARD": 2, "APPOINTED": 2, "CHIEF": 2, "RECOGNITION": 2, "PRIZE": 2, "NOBEL": 2,
    "ECONOMY": 3, "TECH": 3, "FINANCE": 3, "BANK": 3, "RBI": 3, "PORT": 3, "TRADE": 3, "BUDGET": 3, "INFRASTRUCTURE": 3,
    "SPORTS": 4, "GAME": 4, "ATHLETE": 4, "GOLD": 4, "MEDAL": 4, "CHAMPIONSHIP": 4, "TROPHY": 4, "CRICKET": 4, "FOOTBALL": 4,
    "SCIENCE": 5, "SPACE": 5, "ISRO": 5, "NASA": 5, "RESEARCH": 5, "SATELLITE": 5, "QUANTUM": 5, "TECHNOLOGY": 5,
    "DEFENCE": 6, "DEFENSE": 6, "SECURITY": 6, "MILITARY": 6, "NAVY": 6, "ARMY": 6, "AIR FORCE": 6, "MISSILE": 6,
    "ENVIRONMENT": 7, "ECOLOGY": 7, "WILDLIFE": 7, "CLIMATE": 7, "FOREST": 7, "TIGER": 7, "DISASTER": 7, "WEATHER": 7, "CULTURE": 7, "ART": 7,
    "INTERNATIONAL": 8, "WORLD": 8, "GLOBAL": 8, "SUMMIT": 8, "FOREIGN": 8, "BILATERAL": 8, "INDEX": 8, "REPORT": 8, "RANKING": 8
}

def get_theme_for_category(category_raw):
    raw_str = str(category_raw or "GENERAL NEWS").strip()
    clean_label = raw_str.replace("_", " ").upper()
    clean_label = " ".join(clean_label.split())

    # Strip any emojis automatically if present
    clean_label = re.sub(r'[^\w\s&,-]', '', clean_label).strip()
    if not clean_label:
        clean_label = "GENERAL NEWS"

    palette_idx = 5
    for kw, idx in KEYWORD_COLOR_MAP.items():
        if kw in clean_label:
            palette_idx = idx
            break
    else:
        palette_idx = abs(hash(clean_label)) % len(DYNAMIC_COLOR_PALETTES)

    pal = DYNAMIC_COLOR_PALETTES[palette_idx]

    return {
        "label": clean_label,
        "primary_color": pal["primary"],
        "gradient": f"linear-gradient(135deg, {pal['primary']} 0%, #0F172A 100%)",
        "badge_bg": pal["badge_bg"],
        "border_color": pal["border"],
        "glow_color": pal["glow"],
        "bullet_dot": "►",
        "accent_text": pal["accent"]
    }

# Fallback dict for backwards compatibility
CATEGORY_THEMES = {
    "BREAKING_NOTICES": get_theme_for_category("BREAKING NOTICE"),
    "SCHEMES_AND_POLICIES": get_theme_for_category("SCHEMES & POLICIES"),
    "APPOINTMENTS_AND_HONOURS": get_theme_for_category("APPOINTMENTS & HONOURS"),
    "ECONOMY_AND_TECH": get_theme_for_category("ECONOMY & TECH"),
    "GENERAL_NEWS": get_theme_for_category("GENERAL NEWS")
}

LAYOUT_VARIANTS = [
    # Variant 0 (Monday): Glassmorphic Floating Hero Card with Radial Dot Matrix
    """
    body {{
      background: #0B0F19;
      background-image: 
        radial-gradient(rgba(255, 255, 255, 0.08) 1.5px, transparent 1.5px),
        radial-gradient(at 0% 0%, {glow_color} 0px, transparent 55%),
        radial-gradient(at 100% 100%, rgba(15, 23, 42, 0.9) 0px, transparent 60%);
      background-size: 32px 32px, 100% 100%, 100% 100%;
    }}
    .main-card {{
      background: rgba(17, 24, 39, 0.85);
      backdrop-filter: blur(24px);
      border: 1.5px solid {border_color};
      border-radius: 28px;
      box-shadow: 0 24px 60px rgba(0, 0, 0, 0.6), 0 0 40px {glow_color};
    }}
    .category-badge {{
      background: {badge_bg};
      border-radius: 30px;
      box-shadow: 0 4px 20px {glow_color};
    }}
    """,

    # Variant 1 (Tuesday): Split-Column Dual Accent Stripe & Line Grid
    """
    body {{
      background: #0F172A;
      background-image: 
        linear-gradient(rgba(255, 255, 255, 0.04) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255, 255, 255, 0.04) 1px, transparent 1px);
      background-size: 40px 40px;
    }}
    .main-card {{
      background: #1E293B;
      border-left: 8px solid {primary_color};
      border-top: 1px solid rgba(255, 255, 255, 0.12);
      border-right: 1px solid rgba(255, 255, 255, 0.12);
      border-bottom: 1px solid rgba(255, 255, 255, 0.12);
      border-radius: 24px;
      box-shadow: 0 20px 45px rgba(0, 0, 0, 0.5);
    }}
    .category-badge {{
      background: {badge_bg};
      border-radius: 30px;
      box-shadow: 0 4px 20px {glow_color};
    }}
    """,

    # Variant 2 (Wednesday): Ambient Halo Glow Card & Diagonal Stripe Pattern
    """
    body {{
      background: #070A14;
      background-image: 
        repeating-linear-gradient(45deg, rgba(255, 255, 255, 0.02) 0, rgba(255, 255, 255, 0.02) 2px, transparent 0, transparent 20px),
        radial-gradient(circle at 50% 40%, {glow_color} 0px, transparent 65%);
    }}
    .main-card {{
      background: rgba(15, 23, 42, 0.92);
      border: 2px solid {primary_color};
      border-radius: 32px;
      box-shadow: 0 0 50px {glow_color}, inset 0 0 30px rgba(0,0,0,0.5);
    }}
    .category-badge {{
      background: {badge_bg};
      border-radius: 30px;
      box-shadow: 0 6px 25px {glow_color};
    }}
    """,

    # Variant 3 (Thursday): Nordic Minimalist Offset Frame & Vignette Texture
    """
    body {{
      background: #0D1117;
      background-image: radial-gradient(circle at 50% 50%, rgba(255,255,255,0.05) 0%, transparent 80%);
    }}
    .main-card {{
      background: #161B22;
      border: 1px solid rgba(255, 255, 255, 0.15);
      outline: 2px dashed {border_color};
      outline-offset: -12px;
      border-radius: 20px;
      box-shadow: 0 25px 50px rgba(0, 0, 0, 0.7);
    }}
    .category-badge {{
      background: {badge_bg};
      border-radius: 30px;
      box-shadow: 0 4px 20px {glow_color};
    }}
    """,

    # Variant 4 (Friday): Full Header Banner Ribbon & Hex Pattern
    """
    body {{
      background: #080D1A;
      background-image: 
        radial-gradient(at 100% 0%, {glow_color} 0px, transparent 50%),
        radial-gradient(at 0% 100%, rgba(15, 23, 42, 0.95) 0px, transparent 60%);
    }}
    .main-card {{
      background: #111827;
      border: 1px solid {border_color};
      border-radius: 24px;
      position: relative;
      overflow: hidden;
      box-shadow: 0 20px 50px rgba(0,0,0,0.6);
    }}
    .category-badge {{
      background: {badge_bg};
      border-radius: 30px;
      box-shadow: 0 4px 20px {glow_color};
    }}
    """,

    # Variant 5 (Saturday): Tech Blueprint Grid Container & Corner Accents
    """
    body {{
      background: #040814;
      background-image: 
        linear-gradient(rgba(255, 255, 255, 0.05) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255, 255, 255, 0.05) 1px, transparent 1px);
      background-size: 50px 50px;
    }}
    .main-card {{
      background: rgba(13, 20, 36, 0.95);
      border: 1px solid rgba(255, 255, 255, 0.2);
      border-top: 4px solid {primary_color};
      border-bottom: 4px solid {primary_color};
      border-radius: 16px;
      box-shadow: 0 20px 45px rgba(0, 0, 0, 0.7);
    }}
    .category-badge {{
      background: {badge_bg};
      border-radius: 30px;
      box-shadow: 0 4px 15px {glow_color};
    }}
    """,

    # Variant 6 (Sunday): Executive Gold Rimmed Card & Particle Glow
    """
    body {{
      background: #0A0E17;
      background-image: 
        radial-gradient(circle at 100% 0%, {glow_color} 0px, transparent 60%),
        radial-gradient(circle at 0% 100%, {glow_color} 0px, transparent 60%);
    }}
    .main-card {{
      background: linear-gradient(180deg, #131A29 0%, #0D131F 100%);
      border: 1.5px solid {border_color};
      border-radius: 30px;
      box-shadow: 0 30px 60px rgba(0, 0, 0, 0.8), 0 0 30px {glow_color};
    }}
    .category-badge {{
      background: {badge_bg};
      border-radius: 30px;
      box-shadow: 0 6px 20px {glow_color};
    }}
    """
]

HTML_TEMPLATE_BASE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;600;700;800&family=Poppins:wght@700;800&display=swap" rel="stylesheet">
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      width: 1080px;
      height: 1080px;
      color: #F8FAFC;
      font-family: 'Plus Jakarta Sans', sans-serif;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      padding: 60px;
      overflow: hidden;
      position: relative;
    }}
    {layout_style}
    .top-bar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      z-index: 10;
    }}
    .category-badge {{
      color: #FFFFFF;
      padding: 12px 28px;
      font-weight: 800;
      font-size: 19px;
      letter-spacing: 1px;
      text-transform: uppercase;
      border-radius: 30px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
    }}
    .date-text {{
      font-size: 20px;
      color: #94A3B8;
      font-weight: 700;
    }}
    .main-card {{
      padding: 48px;
      flex-grow: 1;
      margin: 36px 0;
      display: flex;
      flex-direction: column;
      justify-content: center;
      z-index: 10;
    }}
    .headline {{
      font-size: 44px;
      font-weight: 800;
      line-height: 1.25;
      color: #FFFFFF;
      margin-bottom: 32px;
      letter-spacing: -0.5px;
    }}
    .bullets {{
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 22px;
    }}
    .bullets li {{
      position: relative;
      padding-left: 36px;
      font-size: 22px;
      line-height: 1.55;
      color: #E2E8F0;
      font-weight: 500;
    }}
    .bullets li b {{
      color: #FFD166;
      font-weight: 800;
    }}
    .bullets li::before {{
      content: '{bullet_dot}';
      position: absolute;
      left: 4px;
      color: #FFD166;
      font-size: 14px;
      top: 6px;
    }}
    .footer {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-top: 1px solid rgba(255, 255, 255, 0.12);
      padding-top: 24px;
      z-index: 10;
    }}
    .footer-left {{
      display: flex;
      align-items: center;
      gap: 12px;
    }}
    .brand-icon-sm {{
      width: 36px;
      height: 36px;
      background: linear-gradient(135deg, #6366F1 0%, #3B82F6 100%);
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      box-shadow: 0 6px 15px -3px rgba(99, 102, 241, 0.5);
    }}
    .brand-icon-sm svg {{
      width: 22px;
      height: 22px;
    }}
    .website-text {{
      font-size: 20px;
      font-weight: 700;
      color: #F8FAFC;
      letter-spacing: 0.5px;
    }}
    .footer-right {{
      font-size: 19px;
      font-weight: 600;
      color: #94A3B8;
      letter-spacing: 0.5px;
    }}
  </style>
</head>
<body>
  <div class="top-bar">
    <div class="category-badge">{category_tag}</div>
    <div class="date-text">{date_str}</div>
  </div>

  <div class="main-card">
    <h1 class="headline">{headline}</h1>
    <ul class="bullets">
      {bullet_items_html}
    </ul>
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
      Daily CA Quiz & Practice 🚀
    </div>
  </div>
</body>
</html>
"""

def highlight_keypoint_label(text):
    if not text:
        return ""
    clean = str(text).replace("**", "").replace("*", "").strip()
    
    if "<b>" in clean and "</b>" in clean:
        return clean
    
    if ":" in clean:
        parts = clean.split(":", 1)
        label = parts[0].strip()
        val = parts[1].strip()
        return f"<b>{label}:</b> {val}"
    
    return clean

def render_ca_slides(ca_items):
    day_of_week = datetime.now().weekday() # 0 = Monday, 6 = Sunday
    layout_variant_idx = day_of_week % len(LAYOUT_VARIANTS)
    print(f"[VERBOSE LOG] Starting Dynamic Future-Proof Category Renderer (Day {day_of_week+1}, Structural Layout Variant #{layout_variant_idx+1})...")
    
    if sync_playwright is None:
        print("⚠️ Playwright not installed in local environment. Skipping slide PNG image generation...")
        return []

    rendered_image_paths = []
    today_date_str = datetime.now().strftime("%d %B %Y")
    temp_html_path = os.path.join(SCRIPT_DIR, "temp_ca.html")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for idx, item in enumerate(ca_items, start=1):
                raw_category = item.get("category", "GENERAL NEWS")
                headline = item.get("headline", "")
                bullets = item.get("bullets", [])

                # Smooth rotating aesthetic color palette per slide (zero category tags)
                pal = DYNAMIC_COLOR_PALETTES[(idx - 1) % len(DYNAMIC_COLOR_PALETTES)]
                theme_info = {
                    "primary_color": pal["primary"],
                    "gradient": f"linear-gradient(135deg, {pal['primary']} 0%, #0F172A 100%)",
                    "badge_bg": pal["badge_bg"],
                    "border_color": pal["border"],
                    "glow_color": pal["glow"],
                    "bullet_dot": "►",
                    "accent_text": pal["accent"]
                }

                raw_layout_css = LAYOUT_VARIANTS[layout_variant_idx]
                layout_style = raw_layout_css.format(
                    primary_color=theme_info["primary_color"],
                    gradient=theme_info["gradient"],
                    badge_bg=theme_info["badge_bg"],
                    border_color=theme_info["border_color"],
                    glow_color=theme_info["glow_color"]
                )

                formatted_bullets = [highlight_keypoint_label(b) for b in bullets]
                bullet_items_html = "\n".join([f"<li>{b}</li>" for b in formatted_bullets])

                final_html = HTML_TEMPLATE_BASE.format(
                    layout_style=layout_style,
                    category_tag="CURRENT AFFAIRS",
                    date_str=today_date_str,
                    headline=headline,
                    bullet_items_html=bullet_items_html,
                    bullet_dot=theme_info["bullet_dot"],
                    badge_bg=theme_info["badge_bg"],
                    glow_color=theme_info["glow_color"],
                    accent_text=theme_info["accent_text"]
                )

                with open(temp_html_path, "w", encoding="utf-8") as f:
                    f.write(final_html)

                output_png_filename = f"ca_slide_{idx}.png"
                output_png_path = os.path.join(OUTPUT_DIR, output_png_filename)

                page = browser.new_page(viewport={"width": 1080, "height": 1080})
                file_url = f"file:///{temp_html_path.replace(os.sep, '/')}"
                page.goto(file_url, wait_until="networkidle")
                page.screenshot(path=output_png_path)
                rendered_image_paths.append(output_png_path)
                page.close()

                print(f"✅ Slide {idx}/{len(ca_items)} rendered: {output_png_filename} (Layout Variant #{layout_variant_idx+1})")
        finally:
            browser.close()
            if os.path.exists(temp_html_path):
                try:
                    os.remove(temp_html_path)
                except Exception:
                    pass

    print(f"🎉 Successfully rendered {len(rendered_image_paths)} dynamic future-proof Current Affairs slides.")
    return rendered_image_paths

if __name__ == "__main__":
    sample_slides = [
        {
            "category": "SCHEMES & POLICIES",
            "headline": "Odisha Launches Subhadra Yojana Guidelines",
            "bullets": [
                "Financial Outlay: State Cabinet approves scheme implementation details.",
                "Target Beneficiaries: Over 1 Crore women across Odisha eligible.",
                "Official Portal: Visit official portal for registration steps."
            ]
        }
    ]
    render_ca_slides(sample_slides)
