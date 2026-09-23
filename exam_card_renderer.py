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
EXAM_THEMES = {
    "RECRUITMENT": {
        "badge_text": "📢 OFFICIAL RECRUITMENT NOTIFICATION",
        "badge_gradient": "linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%)",
        "bg_color": "#0B1120",
        "radial_1": "rgba(37, 99, 235, 0.45)",
        "radial_2": "rgba(99, 102, 241, 0.25)",
        "card_bg": "linear-gradient(145deg, rgba(15, 23, 42, 0.95), rgba(10, 15, 30, 0.98))",
        "border_color": "#3B82F6",
        "accent_color": "#60A5FA",
        "glow_color": "rgba(37, 99, 235, 0.35)",
        "bullet_icon": "📌"
    },
    "APPLICATION": {
        "badge_text": "🚀 APPLICATION WINDOW OPEN",
        "badge_gradient": "linear-gradient(135deg, #059669 0%, #047857 100%)",
        "bg_color": "#061A14",
        "radial_1": "rgba(5, 150, 105, 0.45)",
        "radial_2": "rgba(16, 185, 129, 0.25)",
        "card_bg": "linear-gradient(145deg, rgba(6, 40, 30, 0.95), rgba(4, 25, 20, 0.98))",
        "border_color": "#10B981",
        "accent_color": "#34D399",
        "glow_color": "rgba(5, 150, 105, 0.35)",
        "bullet_icon": "🚀"
    },
    "EXAM_DATE": {
        "badge_text": "📅 EXAM DATE / SCHEDULE ANNOUNCED",
        "badge_gradient": "linear-gradient(135deg, #4F46E5 0%, #4338CA 100%)",
        "bg_color": "#0D0E25",
        "radial_1": "rgba(79, 70, 229, 0.45)",
        "radial_2": "rgba(99, 102, 241, 0.25)",
        "card_bg": "linear-gradient(145deg, rgba(22, 24, 60, 0.95), rgba(12, 14, 38, 0.98))",
        "border_color": "#6366F1",
        "accent_color": "#818CF8",
        "glow_color": "rgba(79, 70, 229, 0.35)",
        "bullet_icon": "📅"
    },
    "ADMIT_CARD": {
        "badge_text": "🎟️ ADMIT CARD / HALL TICKET OUT",
        "badge_gradient": "linear-gradient(135deg, #0284C7 0%, #0369A1 100%)",
        "bg_color": "#071422",
        "radial_1": "rgba(2, 132, 199, 0.50)",
        "radial_2": "rgba(56, 189, 248, 0.30)",
        "card_bg": "linear-gradient(145deg, rgba(10, 32, 54, 0.95), rgba(5, 18, 32, 0.98))",
        "border_color": "#38BDF8",
        "accent_color": "#7DD3FC",
        "glow_color": "rgba(2, 132, 199, 0.40)",
        "bullet_icon": "🎟️"
    },
    "RESULT": {
        "badge_text": "🏆 RESULT & MERIT LIST DECLARED",
        "badge_gradient": "linear-gradient(135deg, #D97706 0%, #B45309 100%)",
        "bg_color": "#1C1103",
        "radial_1": "rgba(217, 119, 6, 0.45)",
        "radial_2": "rgba(245, 158, 11, 0.25)",
        "card_bg": "linear-gradient(145deg, rgba(45, 25, 6, 0.95), rgba(30, 15, 4, 0.98))",
        "border_color": "#F59E0B",
        "accent_color": "#FBBF24",
        "glow_color": "rgba(217, 119, 6, 0.35)",
        "bullet_icon": "🏆"
    },
    "CORRIGENDUM": {
        "badge_text": "✏️ IMPORTANT OFFICIAL NOTICE",
        "badge_gradient": "linear-gradient(135deg, #7C3AED 0%, #6D28D9 100%)",
        "bg_color": "#130826",
        "radial_1": "rgba(124, 58, 237, 0.45)",
        "radial_2": "rgba(139, 92, 246, 0.25)",
        "card_bg": "linear-gradient(145deg, rgba(32, 14, 62, 0.95), rgba(20, 8, 40, 0.98))",
        "border_color": "#8B5CF6",
        "accent_color": "#A78BFA",
        "glow_color": "rgba(124, 58, 237, 0.35)",
        "bullet_icon": "✏️"
    }
}

def detect_exam_scenario(title: str, update_type: str = "") -> str:
    combined = f"{title} {update_type}".lower()
    if any(k in combined for k in ["admit card", "hall ticket", "call letter", "city slip"]):
        return "ADMIT_CARD"
    elif any(k in combined for k in ["exam date", "schedule", "exam calendar", "rescheduled", "postponed", "shift timing"]):
        return "EXAM_DATE"
    elif any(k in combined for k in ["result", "merit list", "scorecard", "cut-off", "cutoff", "answer key", "selection list"]):
        return "RESULT"
    elif any(k in combined for k in ["apply online", "application start", "registration open", "last date"]):
        return "APPLICATION"
    elif any(k in combined for k in ["corrigendum", "correction window", "notice", "candidature"]):
        return "CORRIGENDUM"
    else:
        return "RECRUITMENT"

def render_exam_alert_card(article_data: dict, output_path: str = None) -> str:
    """
    Renders an authoritative 1080x1080 PNG visual card for an Official Exam Notification.
    Returns the path to the saved PNG image.
    """
    if not output_path:
        output_path = os.path.join(OUTPUT_DIR, "exam_update_slide.png")

    title = str(article_data.get("title", "Official Exam Notification")).strip()
    org_name = str(article_data.get("organization") or article_data.get("exam_board") or "Official Authority").strip()
    exam_name = str(article_data.get("exam") or article_data.get("target_exam") or org_name).strip()
    vacancies = str(article_data.get("vacancies", "")).strip()
    eligibility = str(article_data.get("eligibility", "")).strip()
    dates = str(article_data.get("dates", "")).strip()
    exam_schedule = str(article_data.get("exam_schedule", "")).strip()
    official_link = str(article_data.get("official_link") or article_data.get("official_source") or "Official Portal").strip()
    bullets = article_data.get("bullets", [])

    # Scenario Detection & Theme Selection
    scenario = detect_exam_scenario(title, article_data.get("update_type", ""))
    theme = EXAM_THEMES.get(scenario, EXAM_THEMES["RECRUITMENT"])

    # Adaptive Typography (scale font if title is long)
    if len(title) > 75:
        headline_size = "26px"
        headline_line_height = "1.3"
    elif len(title) > 50:
        headline_size = "30px"
        headline_line_height = "1.3"
    else:
        headline_size = "34px"
        headline_line_height = "1.32"

    # Extract official domain host cleanly
    try:
        if official_link.startswith("http"):
            domain = urllib.parse.urlparse(official_link).netloc.replace("www.", "")
        else:
            domain = official_link
    except Exception:
        domain = "Official Portal"

    # Format date label
    today_label = datetime.now().strftime("%d %B %Y")

    # Build Stat Pills Grid based on available metrics
    stat_pills_html = []
    if vacancies and vacancies.lower() not in ["n/a", "none", "", "check official", "refer to notice"]:
        stat_pills_html.append(f"""
        <div class="stat-pill">
            <span class="stat-icon">👥</span>
            <div class="stat-text">
                <div class="stat-label">TOTAL VACANCIES</div>
                <div class="stat-val">{vacancies}</div>
            </div>
        </div>
        """)
    
    if dates and dates.lower() not in ["n/a", "none", "", "check official"]:
        stat_pills_html.append(f"""
        <div class="stat-pill">
            <span class="stat-icon">📅</span>
            <div class="stat-text">
                <div class="stat-label">SCHEDULE / DATES</div>
                <div class="stat-val">{dates}</div>
            </div>
        </div>
        """)
    elif exam_schedule and exam_schedule.lower() not in ["n/a", "none", "", "check official"]:
        stat_pills_html.append(f"""
        <div class="stat-pill">
            <span class="stat-icon">⏳</span>
            <div class="stat-text">
                <div class="stat-label">EXAM SCHEDULE</div>
                <div class="stat-val">{exam_schedule}</div>
            </div>
        </div>
        """)

    if eligibility and eligibility.lower() not in ["n/a", "none", "", "check official"] and len(stat_pills_html) < 2:
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

    stat_grid_block = ""
    if stat_pills_html:
        stat_grid_block = f'<div class="stat-grid">{"".join(stat_pills_html[:2])}</div>'

    # Build Bullet Points List (up to 3 concise, high-impact points)
    bullets_html_list = []
    for b in bullets[:3]:
        clean_b = str(b).strip().replace("**", "").replace("*", "")
        if ":" in clean_b:
            parts = clean_b.split(":", 1)
            b_formatted = f"<b>{parts[0].strip()}:</b> {parts[1].strip()}"
        else:
            b_formatted = clean_b
        if b_formatted:
            bullets_html_list.append(f"<li>{b_formatted}</li>")

    if not bullets_html_list:
        bullets_html_list.append("<li>Official recruitment notification and detailed examination schedule released.</li>")
        bullets_html_list.append("<li>Candidates can verify eligibility, syllabus, and online application guidelines.</li>")

    bullets_block = "\n".join(bullets_html_list)

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
      padding: 48px;
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
      position: relative;
      display: flex;
      justify-content: space-between;
      align-items: center;
      width: 100%;
      z-index: 10;
    }}

    .category-badge {{
      background: {theme["badge_gradient"]};
      color: #FFFFFF;
      padding: 11px 22px;
      border-radius: 14px;
      font-weight: 900;
      font-size: 17px;
      letter-spacing: 0.8px;
      text-transform: uppercase;
      box-shadow: 0 6px 25px {theme["glow_color"]};
      display: flex;
      align-items: center;
      gap: 10px;
      border: 1px solid rgba(255, 255, 255, 0.35);
    }}

    .board-tag {{
      position: absolute;
      left: 50%;
      transform: translateX(-50%);
      background: rgba(255, 255, 255, 0.15);
      backdrop-filter: blur(16px);
      border: 1.5px solid rgba(255, 255, 255, 0.32);
      color: #FFFFFF;
      padding: 10px 24px;
      border-radius: 14px;
      font-weight: 900;
      font-size: 18px;
      letter-spacing: 1.2px;
      text-transform: uppercase;
      box-shadow: 0 6px 20px rgba(0, 0, 0, 0.35);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 20;
    }}

    .date-text {{
      background: rgba(255, 255, 255, 0.08);
      backdrop-filter: blur(12px);
      border: 1px solid rgba(255, 255, 255, 0.16);
      padding: 10px 18px;
      border-radius: 12px;
      font-size: 16px;
      color: #E2E8F0;
      font-weight: 800;
      display: flex;
      align-items: center;
      gap: 6px;
      letter-spacing: 0.5px;
    }}

    .main-card {{
      background: {theme["card_bg"]};
      border: 2px solid {theme["border_color"]};
      border-radius: 26px;
      padding: 38px 44px;
      flex-grow: 1;
      margin: 20px 0;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      box-shadow: 0 0 60px {theme["glow_color"]}, inset 0 1px 0 rgba(255, 255, 255, 0.15);
      z-index: 10;
      position: relative;
    }}

    .card-header {{
      margin-bottom: 12px;
    }}

    .exam-board-title {{
      font-size: 19px;
      font-weight: 800;
      color: {theme["accent_color"]};
      text-transform: uppercase;
      letter-spacing: 1.5px;
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
      letter-spacing: -0.2px;
    }}

    .stat-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 14px;
      margin: 12px 0;
    }}

    .stat-pill {{
      background: rgba(255, 255, 255, 0.07);
      border: 1px solid rgba(255, 255, 255, 0.15);
      border-radius: 14px;
      padding: 12px 18px;
      display: flex;
      align-items: center;
      gap: 12px;
    }}

    .stat-icon {{
      font-size: 24px;
    }}

    .stat-text {{
      display: flex;
      flex-direction: column;
    }}

    .stat-label {{
      font-size: 12px;
      font-weight: 800;
      color: {theme["accent_color"]};
      letter-spacing: 0.8px;
      text-transform: uppercase;
    }}

    .stat-val {{
      font-size: 17px;
      font-weight: 800;
      color: #FFFFFF;
    }}

    .bullets-container {{
      margin: 8px 0;
    }}

    .bullets {{
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }}

    .bullets li {{
      position: relative;
      padding-left: 32px;
      font-size: 20px;
      line-height: 1.42;
      color: #F1F5F9;
      font-weight: 500;
    }}

    .bullets li b {{
      color: {theme["accent_color"]};
      font-weight: 800;
    }}

    .bullets li::before {{
      content: '{theme["bullet_icon"]}';
      position: absolute;
      left: 2px;
      color: {theme["accent_color"]};
      font-size: 17px;
      top: 3px;
    }}

    .official-portal-strip {{
      background: rgba(0, 0, 0, 0.45);
      border: 1px solid rgba(255, 255, 255, 0.15);
      border-radius: 14px;
      padding: 10px 18px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-top: 10px;
    }}

    .portal-label {{
      font-size: 16px;
      font-weight: 700;
      color: #94A3B8;
      display: flex;
      align-items: center;
      gap: 8px;
    }}

    .portal-link {{
      font-size: 17px;
      font-weight: 800;
      color: #38BDF8;
      letter-spacing: 0.5px;
    }}

    .footer {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-top: 1px solid rgba(255, 255, 255, 0.15);
      padding-top: 18px;
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
      font-weight: 800;
      color: #FFFFFF;
      letter-spacing: 0.5px;
    }}

    .footer-right {{
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 17px;
      font-weight: 700;
      color: #CBD5E1;
      letter-spacing: 0.5px;
    }}

    .verified-pill {{
      background: rgba(16, 185, 129, 0.2);
      border: 1px solid rgba(16, 185, 129, 0.5);
      color: #6EE7B7;
      padding: 4px 12px;
      border-radius: 8px;
      font-size: 14px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}
  </style>
</head>
<body>
  <div class="top-bar">
    <div class="category-badge">{theme["badge_text"]}</div>
    <div class="board-tag">{org_name}</div>
    <div class="date-text">📅 {today_label}</div>
  </div>

  <div class="main-card">
    <div class="card-header">
      <div class="exam-board-title">🏛️ {org_name} • {exam_name}</div>
      <h1 class="headline">{title}</h1>
    </div>

    {stat_grid_block}

    <div class="bullets-container">
      <ul class="bullets">
        {bullets_block}
      </ul>
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
