import os
import sys
import re
import json
from typing import Optional, List
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILE_DIR = os.path.join(SCRIPT_DIR, "yt_profile")
STATE_FILE = os.path.join(SCRIPT_DIR, "yt_state.json")

def format_exam_notification_youtube_caption(article_data: dict) -> str:
    """
    Formats a clean, high-impact YouTube Community post for official exam notifications.
    """
    title = article_data.get("title", "Official Exam Notification")
    org = article_data.get("organization") or article_data.get("target_exam") or "Odisha Recruitment Board"
    official_link = article_data.get("official_notification_link") or article_data.get("source_url") or "https://www.ossc.gov.in"
    article_url = article_data.get("article_url") or "https://www.odishaexamprep.in"
    
    bullets = article_data.get("key_highlights") or article_data.get("highlights") or []

    lines = [
        "🚨 OFFICIAL EXAM NOTIFICATION RELEASED!",
        "",
        f"📌 {title}",
        f"🏢 Recruitment Board: {org}",
        ""
    ]

    if bullets:
        lines.append("⚡ Key Highlights & Important Dates:")
        for b in bullets[:4]:
            b_clean = re.sub(r'<[^>]+>', '', str(b)).strip()
            if b_clean:
                lines.append(f"• {b_clean}")
        lines.append("")

    lines.append("🌐 Direct Official Notification Portal:")
    lines.append(f"👉 {official_link}")
    lines.append("")

    if article_url and "generated-uuid" not in article_url:
        lines.append("📖 Read Complete Syllabus & Eligibility Analysis on OdishaExamPrep:")
        lines.append(f"👉 {article_url}")
        lines.append("")

    lines.append("🎯 Practice Daily Mock Tests & Previous Year Papers:")
    lines.append("👉 https://www.odishaexamprep.in/")
    lines.append("")
    lines.append("💬 Join Telegram for Instant Exam PDFs & Alerts: https://t.me/OdishaExamPrep")

    return "\n".join(lines).strip()

def post_exam_update_to_youtube(article_data: dict, image_path: Optional[str] = None) -> bool:
    """
    Publishes an official exam update announcement to YouTube Community.
    """
    caption = format_exam_notification_youtube_caption(article_data)
    print("\n--------------------------------------------------")
    print("[VERBOSE LOG] Publishing Official Exam Notification to YouTube Community...")
    print(f"📌 Exam Title: {article_data.get('title')}")
    print("--------------------------------------------------")

    env_state = os.getenv("YOUTUBE_STORAGE_STATE") or os.getenv("YT_STATE_BASE64")
    if env_state and not os.path.exists(STATE_FILE):
        try:
            raw_val = env_state.strip()
            if raw_val.startswith("{"):
                with open(STATE_FILE, "w", encoding="utf-8") as f:
                    f.write(raw_val)
            else:
                import base64
                decoded = base64.b64decode(raw_val).decode("utf-8")
                with open(STATE_FILE, "w", encoding="utf-8") as f:
                    f.write(decoded)
            print("🔑 Restored yt_state.json from environment variable.")
        except Exception as e:
            print(f"⚠️ Failed to write YOUTUBE_STORAGE_STATE: {e}")

    if not os.path.exists(PROFILE_DIR) and not os.path.exists(STATE_FILE):
        print("⚠️ YouTube Session profile/state not found. YouTube Community post skipped.")
        return False

    is_headless = os.getenv("HEADLESS", "true").lower() == "true" or os.getenv("GITHUB_ACTIONS") == "true"
    print(f"🚀 Launching Chromium browser for YouTube (Headless={is_headless})...")

    try:
        with sync_playwright() as p:
            if os.path.exists(STATE_FILE):
                print("🔑 Using storage state file...")
                browser = p.chromium.launch(headless=is_headless, slow_mo=200)
                context = browser.new_context(
                    storage_state=STATE_FILE,
                    viewport={"width": 1280, "height": 800},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
                )
                page = context.new_page()
            elif os.path.exists(PROFILE_DIR):
                print("👤 Using persistent Chromium user profile...")
                context = p.chromium.launch_persistent_context(
                    user_data_dir=PROFILE_DIR,
                    headless=is_headless,
                    viewport={"width": 1280, "height": 800},
                    args=["--disable-blink-features=AutomationControlled"]
                )
                page = context.pages[0] if context.pages else context.new_page()

            page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            channel_url = "https://www.youtube.com/channel/UCXHAJIDI-ZNiDRadIAHBSPQ/posts"
            print(f"🌐 Navigating to {channel_url}...")
            page.goto(channel_url, wait_until="domcontentloaded", timeout=40000)
            page.wait_for_timeout(4000)

            if "accounts.google.com" in page.url or "signin" in page.url:
                print("⚠️ Redirected to Google Sign-In! Login required for YouTube posting.")
                context.close()
                return False

            print("✅ Logged into YouTube Community page!")

            print("✏️ Opening Community post composer...")
            placeholder = page.locator("#commentbox-placeholder, #placeholder-area").first
            placeholder.click()
            page.wait_for_timeout(2500)

            if image_path and os.path.exists(image_path):
                print(f"🖼️ Activating Image Post mode for banner ({image_path})...")
                img_btn = page.locator("button[aria-label='Add an image']:visible, #image-post-button:visible, button:has-text('Image'):visible").first
                if img_btn.count() > 0:
                    img_btn.click()
                    page.wait_for_timeout(2500)

                print("📤 Uploading image to YouTube dropzone...")
                file_input = page.locator("input[type='file']").first
                file_input.set_input_files([image_path])
                print("⏳ Waiting 8 seconds for image thumbnail to render...")
                page.wait_for_timeout(8000)
            else:
                print("ℹ️ Proceeding with High-Impact Text YouTube Community Announcement...")

            print("📝 Filling Post Caption & Website Link...")
            editor = page.locator("#contenteditable-root[contenteditable='true'], div[contenteditable='true']#contenteditable-root, #textbox").first
            editor.focus()
            
            clean_caption = re.sub(r'<[^>]+>', '', caption)
            editor.fill(clean_caption)
            page.wait_for_timeout(2000)

            print("🚀 Publishing YouTube Community Post...")
            post_btn = page.locator("button:has-text('Post'), [aria-label='Post']").last
            post_btn.click()
            page.wait_for_timeout(6000)

            print("🎉 YouTube Official Exam Notification published successfully!")
            context.close()
            return True
    except Exception as e:
        print(f"⚠️ Error publishing exam notification to YouTube Community: {e}")
        return False
