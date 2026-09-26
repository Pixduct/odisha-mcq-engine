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

def dismiss_dialogs(page):
    """Dismisses cookie consent popups, got-it banners, or overlay dialogs."""
    try:
        selectors = [
            "button[aria-label*='Accept']",
            "button[aria-label*='agree']",
            "button[aria-label*='Dismiss']",
            "ytd-button-renderer#dismiss-button button",
            "#dismiss-button button",
            "tp-yt-paper-button#dismiss-button",
            "button:has-text('Got it')",
            "button:has-text('Dismiss')",
            "button:has-text('Accept all')",
            "button:has-text('I agree')",
            "ytd-modal-with-title-and-button-renderer #dismiss-button button"
        ]
        for sel in selectors:
            btn = page.locator(sel).first
            if btn.count() > 0 and btn.is_visible():
                btn.evaluate("el => el.click()")
                page.wait_for_timeout(500)
    except Exception:
        pass

def format_exam_notification_youtube_caption(article_data: dict) -> str:
    """
    Formats a clean, high-impact YouTube Community post for official exam notifications.
    """
    title = article_data.get("title", "Official Exam Notification")
    org = article_data.get("organization") or article_data.get("target_exam") or "Odisha Recruitment Board"
    official_link = article_data.get("official_link") or article_data.get("official_notification_link") or article_data.get("source_url") or "https://www.ossc.gov.in"
    article_url = article_data.get("article_url") or "https://www.odishaexamprep.in"
    bullets = article_data.get("bullets") or article_data.get("key_highlights") or article_data.get("highlights") or []

    # Category badge resolution
    category_badge = article_data.get("category_badge")
    if not category_badge:
        try:
            from exam_card_renderer import detect_exam_scenario
            cat_info = detect_exam_scenario(title, org)
            category_badge = cat_info.get("badge_text", "📢 OFFICIAL EXAM NOTIFICATION")
        except Exception:
            category_badge = "📢 OFFICIAL EXAM NOTIFICATION"

    clean_badge = category_badge.replace("🚨", "").strip()
    header_line = f"🚨 {clean_badge}!"

    try:
        from shared.telegram import is_valid_metric
    except ImportError:
        def is_valid_metric(val):
            return bool(val and str(val).strip().lower() not in ["n/a", "none", "", "refer to notice"])

    vacancies = str(article_data.get("vacancies", "")).strip()
    dates = str(article_data.get("dates", "")).strip()
    exam_schedule = str(article_data.get("exam_schedule", "")).strip()

    lines = [
        header_line,
        "",
        f"📌 {title}",
        f"🏢 Recruitment Authority: {org}"
    ]

    if is_valid_metric(vacancies):
        lines.append(f"👥 Total Vacancies: {vacancies}")
    if is_valid_metric(dates):
        lines.append(f"📅 Critical Dates: {dates}")
    elif is_valid_metric(exam_schedule):
        lines.append(f"⏳ Exam Schedule: {exam_schedule}")

    lines.append("")

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
    if not image_path:
        image_path = article_data.get("slide_image_path") or article_data.get("cover_image") or article_data.get("image_path")
    if isinstance(image_path, list) and image_path:
        image_path = image_path[0]

    caption = format_exam_notification_youtube_caption(article_data)
    print("\n--------------------------------------------------")
    print("[VERBOSE LOG] Publishing Official Exam Notification to YouTube Community...")
    print(f"📌 Exam Title: {article_data.get('title')}")
    if image_path and os.path.exists(str(image_path)):
        print(f"🖼️ Attached Visual Card: {image_path}")
    else:
        print("ℹ️ No visual card provided — will post text announcement.")
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

            dismiss_dialogs(page)

            if "accounts.google.com" in page.url or "signin" in page.url:
                print("⚠️ Redirected to Google Sign-In! Login required for YouTube posting.")
                context.close()
                return False

            sign_in_btn = page.locator("a[aria-label*='Sign in'], ytd-button-renderer:has-text('Sign in'), a:has-text('Sign in')").first
            if sign_in_btn.count() > 0 and sign_in_btn.is_visible():
                print("⚠️ YouTube session is not authenticated (Sign-in button detected). Session cookies have expired. Refresh YT_STATE_BASE64 via extract_yt_cookies.py.")
                context.close()
                return False

            avatar = page.locator("button#avatar-btn, #avatar-btn, ytd-topbar-menu-button-renderer").first
            if avatar.count() > 0 and avatar.is_visible():
                print("✅ Verified logged in via user avatar!")
            else:
                print("ℹ️ Verified session active (no sign-in banner).")

            print("✏️ Opening Community post composer...")
            placeholder = page.locator("#commentbox-placeholder, #placeholder-area, #contenteditable-root, ytd-commentbox #placeholder").first
            try:
                placeholder.wait_for(state="visible", timeout=10000)
                placeholder.evaluate("el => el.click()")
            except Exception:
                try:
                    placeholder.click(force=True, timeout=3000)
                except Exception:
                    print("⚠️ Community post creation composer not available on this page (User may not have channel owner permissions or session expired).")
                    context.close()
                    return False
            page.wait_for_timeout(2500)
            dismiss_dialogs(page)

            if image_path and os.path.exists(image_path):
                print(f"🖼️ Activating Image Post mode for banner ({image_path})...")
                img_btn = page.locator("button[aria-label='Add an image']:visible, #image-post-button:visible, button:has-text('Image'):visible, ytd-button-renderer[aria-label*='Image']:visible").first
                if img_btn.count() > 0:
                    try:
                        img_btn.evaluate("el => el.click()")
                    except Exception:
                        img_btn.click(force=True)
                    page.wait_for_timeout(2500)

                print("📤 Uploading image to YouTube dropzone...")
                file_input = page.locator("ytd-commentbox input[type='file'], #creation-box input[type='file'], input[type='file']:not(.ytSearchboxComponentHiddenFileInput)").first
                if file_input.count() == 0:
                    print("⚠️ Image dropzone file input not found in post composer.")
                    context.close()
                    return False

                file_input.set_input_files([image_path])
                print("⏳ Waiting 8 seconds for image thumbnail to render...")
                page.wait_for_timeout(8000)
                dismiss_dialogs(page)
            else:
                print("ℹ️ Proceeding with High-Impact Text YouTube Community Announcement...")

            print("📝 Filling Post Caption & Website Link...")
            editor = page.locator("#contenteditable-root[contenteditable='true'], div[contenteditable='true']#contenteditable-root, #textbox[contenteditable='true'], ytd-commentbox #contenteditable-root").first
            try:
                editor.wait_for(state="visible", timeout=10000)
                editor.focus()
            except Exception:
                pass
            
            clean_caption = re.sub(r'<[^>]+>', '', caption)
            try:
                editor.fill(clean_caption)
            except Exception:
                editor.evaluate(f"(el, text) => {{ el.focus(); el.textContent = text; el.dispatchEvent(new Event('input', {{ bubbles: true }})); }}", clean_caption)
            page.wait_for_timeout(2000)

            print("🚀 Publishing YouTube Community Post...")
            post_selectors = [
                "ytd-button-renderer#post-button button:not([disabled]):not([aria-disabled='true'])",
                "#post-button button:not([disabled]):not([aria-disabled='true'])",
                "button:has-text('Post'):not([disabled]):not([aria-disabled='true'])",
                "[aria-label='Post']:not([disabled]):not([aria-disabled='true'])",
                "ytd-button-renderer#post-button button",
                "#post-button button",
                "button:has-text('Post')",
                "[aria-label='Post']"
            ]
            post_btn = None
            for sel in post_selectors:
                candidate = page.locator(sel).last
                if candidate.count() > 0 and candidate.is_visible():
                    post_btn = candidate
                    break

            if not post_btn:
                post_btn = page.locator("button:has-text('Post'), [aria-label='Post']").last

            for _ in range(10):
                is_disabled = post_btn.get_attribute("disabled") is not None or post_btn.get_attribute("aria-disabled") == "true"
                if not is_disabled:
                    break
                page.wait_for_timeout(1000)

            try:
                post_btn.evaluate("el => el.click()")
            except Exception:
                try:
                    post_btn.click(force=True, timeout=8000)
                except Exception as ex_click:
                    print(f"⚠️ Post button click note: {ex_click}")

            page.wait_for_timeout(6000)

            print("🎉 YouTube Official Exam Notification published successfully!")
            context.close()
            return True
    except Exception as e:
        print(f"⚠️ Error publishing exam notification to YouTube Community: {e}")
        return False
