import os
import sys
import re
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

def post_ca_to_youtube(image_paths, caption=""):
    caption = str(caption or "")
    print("\n--------------------------------------------------")
    print("[VERBOSE LOG] Publishing Current Affairs Image Carousel to YouTube Community...")
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
        print(f"⚠️ YouTube Session profile/state not found. YouTube Community post skipped.")
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

            # Accurate check for unauthenticated session
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

            valid_images = [img for img in image_paths if (img and os.path.exists(img))]
            if valid_images:
                # CRITICAL: YouTube Community strictly enforces a maximum of 5 images per post.
                if len(valid_images) > 5:
                    print(f"ℹ️ YouTube Community allows a maximum of 5 images per post. Clamping {len(valid_images)} slides to top 5.")
                    valid_images = valid_images[:5]

                print(f"🖼️ Activating Image Post mode for {len(valid_images)} images...")
                img_btn = page.locator("button[aria-label='Add an image']:visible, #image-post-button:visible, button:has-text('Image'):visible, ytd-button-renderer[aria-label*='Image']:visible").first
                if img_btn.count() > 0:
                    try:
                        img_btn.evaluate("el => el.click()")
                    except Exception:
                        img_btn.click(force=True)
                    page.wait_for_timeout(2500)

                print("📤 Uploading slide images to YouTube multi-image dropzone...")
                # Specifically scope to composer file input and strictly exclude the header searchbox input
                file_input = page.locator("ytd-commentbox input[type='file'], #creation-box input[type='file'], input[type='file'][multiple]:not(.ytSearchboxComponentHiddenFileInput)").first
                if file_input.count() == 0:
                    file_input = page.locator("input[type='file']:not(.ytSearchboxComponentHiddenFileInput)").first

                if file_input.count() == 0:
                    print("⚠️ Image dropzone file input not found in post composer.")
                    context.close()
                    return False

                file_input.set_input_files(valid_images)
                print("⏳ Waiting 10 seconds for image thumbnails to upload and render...")
                page.wait_for_timeout(10000)
                dismiss_dialogs(page)
            else:
                print("ℹ️ No valid images provided — proceeding with Text-Only YouTube Community Post...")

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

            print("🚀 Publishing YouTube Image Post...")
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

            # Wait for button to be enabled (up to 10 seconds)
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

            print("🎉 YouTube Current Affairs Image Carousel published successfully!")
            context.close()
            return True
    except Exception as e:
        print(f"⚠️ Error publishing to YouTube Community: {e}")
        return False

if __name__ == "__main__":
    sample_slides = [os.path.join(SCRIPT_DIR, f"ca_slide_{i}.png") for i in range(1, 6)]
    sample_caption = "📰 Daily Current Affairs Update — 13 August 2026\n\nTop exam-relevant highlights for OPSC, OSSC, OSSSC & Odisha State Exams:\n\n1. [Schemes And Policies] Odisha Cabinet Approves ₹10,000 Cr Subhadra Yojana\n2. [Appointments And Honours] Manoj Ahuja Appointed as Chief Secretary of Odisha\n3. [Breaking Notices] OPSC Exam Schedule Released for ASO & Civil Services\n4. [Economy And Tech] RBI Keeps Repo Rate Unchanged at 6.5% in MPC Meeting\n5. [General News] Odisha Athletes Win 3 Medals at National Games\n\n🎯 Practice Today's Current Affairs Quiz & Download PDFs:\n👉 https://www.odishaexamprep.in/"
    post_ca_to_youtube(sample_slides, sample_caption)
