import os
import sys
import json
import time
import requests
from datetime import datetime
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "")

DAY_NAMES = [
    "MONDAY (Day 1 - Glassmorphic Hero Grid)",
    "TUESDAY (Day 2 - Split-Column Dual Accent Stripe)",
    "WEDNESDAY (Day 3 - Ambient Halo Glow Card)",
    "THURSDAY (Day 4 - Nordic Minimalist Offset Frame)",
    "FRIDAY (Day 5 - Vivid Header Banner Ribbon)",
    "SATURDAY (Day 6 - Tech Blueprint Grid Container)",
    "SUNDAY (Day 7 - Executive Gold Rimmed Card)"
]

# Internal design layout test script
from ca_renderer import CATEGORY_THEMES, LAYOUT_VARIANTS, HTML_TEMPLATE_BASE, highlight_keypoint_label

def send_telegram_media_group(bot_token, chat_id, image_paths, caption=""):
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMediaGroup"
        media = []
        files = {}

        for idx, path in enumerate(image_paths):
            file_key = f"photo_{idx}"
            files[file_key] = open(path, "rb")
            media_item = {
                "type": "photo",
                "media": f"attach://{file_key}"
            }
            if idx == 0:
                media_item["caption"] = caption[:1024]
                media_item["parse_mode"] = "HTML"
            media.append(media_item)

        payload = {
            "chat_id": chat_id,
            "media": json.dumps(media),
            "disable_notification": False
        }

        res = requests.post(url, data=payload, files=files, timeout=30)
        for f in files.values():
            f.close()

        return res.ok
    except Exception as e:
        print(f"❌ Error sending Telegram media group: {e}")
        return False

def preview_day(day_idx, ca_items, p):
    day_name = DAY_NAMES[day_idx]
    print(f"\n==================================================")
    print(f"🎨 Generating 5-Slide Category Color Preview for {day_name}...")
    print(f"==================================================")

    today_date_str = datetime.now().strftime("%d %B %Y")
    temp_html_path = os.path.join(SCRIPT_DIR, "temp_preview.html")
    slide_image_paths = []

    browser = p.chromium.launch(headless=True)

    used_summary = []
    for idx, item in enumerate(ca_items, start=1):
        category = item.get("category", "GENERAL_NEWS")
        headline = item.get("headline", "")
        bullets = item.get("bullets", [])

        theme_info = CATEGORY_THEMES.get(category, CATEGORY_THEMES["GENERAL_NEWS"])

        raw_layout_css = LAYOUT_VARIANTS[day_idx]
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
            category_tag=theme_info["label"],
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

        output_png_filename = f"preview_day{day_idx+1}_slide{idx}.png"
        output_png_path = os.path.join(SCRIPT_DIR, output_png_filename)

        page = browser.new_page(viewport={"width": 1080, "height": 1080})
        file_url = f"file:///{temp_html_path.replace(os.sep, '/')}"
        page.goto(file_url, wait_until="networkidle")
        page.screenshot(path=output_png_path)
        page.close()

        slide_image_paths.append(output_png_path)
        used_summary.append(f"• Slide {idx}: {theme_info['label']}")

    browser.close()

    if os.path.exists(temp_html_path):
        os.remove(temp_html_path)

    caption = (
        f"📅 <b>CATEGORY BRAND COLOR PREVIEW: {day_name}</b>\n\n"
        f"<b>Category Colors & Layout Structural Variant #{day_idx+1}:</b>\n" +
        "\n".join(used_summary) + "\n\n"
        f"🌐 <b>Website:</b> https://www.odishaexamprep.in/"
    )

    success = send_telegram_media_group(TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_CHAT_ID, slide_image_paths, caption=caption)
    if success:
        print(f"✅ Successfully sent {day_name} preview album to Admin Bot!")
    else:
        print(f"❌ Failed to send {day_name} preview album.")

    for p_path in slide_image_paths:
        if os.path.exists(p_path):
            os.remove(p_path)

def main():
    ca_data = get_fallback_ca_items()
    if isinstance(ca_data, dict):
        ca_items = ca_data.get("top_slides", [])
    else:
        ca_items = ca_data

    with sync_playwright() as p:
        for day_idx in range(7):
            preview_day(day_idx, ca_items, p)
            time.sleep(2)

if __name__ == "__main__":
    main()
