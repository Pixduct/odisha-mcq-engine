import os
import sys
import json
import base64
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILE_DIR = os.path.join(SCRIPT_DIR, "yt_profile")
STATE_FILE = os.path.join(SCRIPT_DIR, "yt_state.json")
IMAGE_FILE = os.path.join(SCRIPT_DIR, "output_mcq.png")

def post_to_youtube(data=None):
    if data is None:
        data = {
            "Target_Exam": "Daily MCQ",
            "Question_Text": "What is the normal blood pH in the human body?",
            "Option_A": "6.8",
            "Option_B": "7.4",
            "Option_C": "8",
            "Option_D": "7",
            "Correct_Option": "B",
            "Explanation": "Human blood pH is strictly maintained between 7.35 and 7.45."
        }

    env_state = os.getenv("YOUTUBE_STORAGE_STATE") or os.getenv("YT_STATE_BASE64")
    if env_state and not os.path.exists(STATE_FILE):
        try:
            # Check if it is base64 encoded
            try:
                decoded = base64.b64decode(env_state).decode('utf-8')
                if "{" in decoded and "}" in decoded:
                    env_state = decoded
            except Exception:
                pass
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                f.write(env_state)
            print("🔑 Restored yt_state.json from environment variable.")
        except Exception as e:
            print(f"⚠️ Failed to write YOUTUBE_STORAGE_STATE: {e}")

    if not os.path.exists(PROFILE_DIR) and not os.path.exists(STATE_FILE):
        print(f"❌ Session profile not found. Skipping YouTube Community post.")
        return False

    is_headless = os.getenv("HEADLESS", "true").lower() == "true" or os.getenv("GITHUB_ACTIONS") == "true"
    print(f"🚀 Launching Chromium browser (Headless={is_headless})...")

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
        page.goto(channel_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(4000)

        if "accounts.google.com" in page.url or "signin" in page.url:
            print("❌ Redirected to Google Sign-In! Login required.")
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
        page.wait_for_timeout(2000)

        print("🎯 Activating Quiz mode...")
        quiz_btn = page.locator("button[aria-label='Add a quiz'], button:has-text('Quiz')").first
        quiz_btn.evaluate("el => el.click()")
        page.wait_for_timeout(2000)

        target_exam = str(data.get("Target_Exam", "")).strip()
        question_text = str(data.get("Question_Text", "")).strip()
        full_question = f"[{target_exam}] {question_text}" if target_exam else question_text

        print(f"📝 Entering Question: {full_question}")
        q_editor = page.locator("#contenteditable-root[contenteditable='true'], div[contenteditable='true']#contenteditable-root, #textbox").first
        q_editor.focus()
        q_editor.fill(full_question)
        page.wait_for_timeout(1000)

        options = [
            str(data.get("Option_A", "")).strip(),
            str(data.get("Option_B", "")).strip(),
            str(data.get("Option_C", "")).strip(),
            str(data.get("Option_D", "")).strip()
        ]
        options = [opt for opt in options if opt]

        add_answer_btn = page.locator("button[aria-label='Add answer'], button:has-text('Add answer')").first
        while True:
            answer_fields = page.locator("textarea[placeholder*='Answer'], #textarea[placeholder*='Answer']").all()
            if len(answer_fields) >= len(options):
                break
            if add_answer_btn.is_visible():
                print("➕ Clicking 'Add answer' button...")
                add_answer_btn.evaluate("el => el.click()")
                page.wait_for_timeout(1000)
            else:
                break

        answer_fields = page.locator("textarea[placeholder*='Answer'], #textarea[placeholder*='Answer']").all()
        for idx, opt_text in enumerate(options):
            if idx < len(answer_fields):
                print(f"🔹 Setting Option {chr(65+idx)}: {opt_text}")
                answer_fields[idx].focus()
                answer_fields[idx].fill(opt_text)
                page.wait_for_timeout(500)

        correct_raw = str(data.get("Correct_Option", "A")).strip().upper()
        mapping = {"A": 0, "B": 1, "C": 2, "D": 3, "1": 0, "2": 1, "3": 2, "4": 3}
        correct_idx = mapping.get(correct_raw, 0)

        radios = page.locator("tp-yt-paper-radio-button, [role='radio'], #radio-button").all()
        if len(radios) > correct_idx:
            print(f"✅ Marking Correct Answer Option {chr(65+correct_idx)}...")
            radios[correct_idx].evaluate("el => el.click()")
            page.wait_for_timeout(1000)

        explanation = str(data.get("Explanation", "")).strip()
        cta_text = "Practice at https://www.odishaexamprep.in/ 🚀 | Join Telegram: https://t.me/OdishaExamPrepOfficial 📢"
        full_explanation = f"{explanation} | {cta_text}" if explanation else cta_text

        exp_field = page.locator("textarea[placeholder*='Explain why'], #textarea[placeholder*='Explain']").first
        if exp_field.is_visible():
            print(f"💡 Adding explanation & CTA: {full_explanation[:50]}...")
            exp_field.fill(full_explanation[:200])
            page.wait_for_timeout(500)

        print("🚀 Publishing YouTube Quiz post...")
        post_btn = page.locator("button:has-text('Post'), [aria-label='Post']").last
        post_btn.evaluate("el => el.click()")
        page.wait_for_timeout(5000)

        print("🎉 YouTube Quiz Post published successfully!")
        context.close()
        return True

def post_to_youtube_poll(data=None):
    if data is None:
        data = {
            "Target_Exam": "OSSC CGL",
            "Question_Text": "You studied a chapter 5 times but still forget it during a mock test. What is most likely missing?",
            "Option_A": "More highlighting",
            "Option_B": "Active recall testing",
            "Option_C": "Rereading notes",
            "Option_D": "Longer study sessions",
            "Explanation": "Rereading creates passive familiarity, while active recall forces brain retrieval, building lasting memory."
        }

    env_state = os.getenv("YOUTUBE_STORAGE_STATE")
    if env_state and not os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                f.write(env_state)
            print("🔑 Restored yt_state.json from YOUTUBE_STORAGE_STATE environment variable.")
        except Exception as e:
            print(f"⚠️ Failed to write YOUTUBE_STORAGE_STATE: {e}")

    if not os.path.exists(PROFILE_DIR) and not os.path.exists(STATE_FILE):
        print(f"❌ Session profile not found. Skipping YouTube Community post.")
        return False

    is_headless = os.getenv("HEADLESS", "true").lower() == "true" or os.getenv("GITHUB_ACTIONS") == "true"
    print(f"🚀 Launching Chromium browser for Text Poll (Headless={is_headless})...")

    with sync_playwright() as p:
        if os.path.exists(STATE_FILE):
            print("🔑 Using storage state file...")
            browser = p.chromium.launch(headless=is_headless, slow_mo=200)
            context = browser.new_context(
                storage_state=STATE_FILE,
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            )
            page = context.pages[0] if context.pages else context.new_page()
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
        page.goto(channel_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(4000)

        if "accounts.google.com" in page.url or "signin" in page.url:
            print("❌ Redirected to Google Sign-In! Login required.")
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
        page.wait_for_timeout(3000)

        print("🎯 Activating Text Poll mode (NOT Quiz)...")
        try:
            page.wait_for_selector("button[aria-label='Add a text poll'], button[aria-label*='text poll' i], button:has-text('Text poll')", state="visible", timeout=10000)
        except Exception:
            pass

        poll_btn = page.locator("button[aria-label='Add a text poll'], button[aria-label*='text poll' i], button:has-text('Text poll')").first
        if poll_btn.is_visible():
            print("✅ Found visible Text Poll button!")
            poll_btn.evaluate("el => el.click()")
            page.wait_for_timeout(2000)
        else:
            print("⚠️ Searching fallback toolbar buttons...")
            all_btns = page.locator("button, tp-yt-paper-icon-button").all()
            for b in all_btns:
                label = ((b.get_attribute("aria-label") or "") + " " + (b.inner_text() or "")).lower()
                if "poll" in label and "quiz" not in label and "image" not in label:
                    poll_btn = b
                    print(f"✅ Found Text Poll button via label match: '{label}'")
                    break

            if poll_btn:
                poll_btn.evaluate("el => el.click()")
                page.wait_for_timeout(2000)
            else:
                print("⚠️ Falling back to Text poll button click...")
                page.locator("button:has-text('Text poll')").first.evaluate("el => el.click()")
                page.wait_for_timeout(2000)

        target_exam = str(data.get("Target_Exam", "")).strip()
        question_text = str(data.get("Question_Text", "")).strip()
        explanation = str(data.get("Explanation", "")).strip()
        cta_text = (
            "🎯 Practice Mock Tests & Question Banks: https://www.odishaexamprep.in/ 🚀\n"
            "📲 Join Telegram Channel for Daily PDF & Notes: https://t.me/OdishaExamPrepOfficial 📢"
        )
        
        full_question = (
            f"[{target_exam}] {question_text}\n\n"
            f"💡 Insights: {explanation}\n\n"
            f"{cta_text}"
        ) if target_exam else (
            f"{question_text}\n\n"
            f"💡 Insights: {explanation}\n\n"
            f"{cta_text}"
        )

        print(f"📝 Typing Question & Insights into composer...")
        q_editor = page.locator("#contenteditable-root, div[contenteditable='true'], textarea[placeholder*='Ask'], #textbox").first
        q_editor.click(force=True)
        q_editor.focus()
        page.keyboard.type(full_question, delay=5)
        page.wait_for_timeout(1000)

        options = [
            str(data.get("Option_A", "")).strip(),
            str(data.get("Option_B", "")).strip(),
            str(data.get("Option_C", "")).strip(),
            str(data.get("Option_D", "")).strip()
        ]
        options = [opt for opt in options if opt]

        print("🎯 Waiting for Text Poll option inputs to render...")
        page.wait_for_timeout(2500)

        composer = page.locator("ytd-backstage-post-dialog-renderer, #simplebox, #dialog, ytd-single-option-survey-renderer").first
        if not composer.is_visible():
            composer = page.locator("body")

        # Dynamically click "Add option" until we have enough visible fields for all options (up to 4)
        for target_count in range(3, len(options) + 1):
            all_inps = composer.locator("ytd-backstage-poll-choice-renderer input, ytd-select-poll-type-post-renderer input, tp-yt-paper-input input, input[aria-label*='Option' i], input[placeholder*='Option' i]").all()
            visible_inps = [inp for inp in all_inps if inp.is_visible()]
            if len(visible_inps) >= len(options):
                break
            
            add_btn = composer.locator("button[aria-label*='Add' i], button:has-text('Add option'), button:has-text('Add another option'), button:has-text('Add choice'), #add-option-button, tp-yt-paper-button:has-text('Add')").first
            if add_btn.is_visible():
                print(f"➕ Clicking 'Add option' button for Option {target_count}...")
                add_btn.click(force=True)
                page.wait_for_timeout(1500)
            else:
                print("⚠️ Add option button not visible directly, searching fallback Add option...")
                page.locator("button:has-text('Add option'), button:has-text('Add choice'), button:has-text('Add another option')").first.click(force=True)
                page.wait_for_timeout(1500)

        all_inps = composer.locator("ytd-backstage-poll-choice-renderer input, ytd-select-poll-type-post-renderer input, tp-yt-paper-input input, input[aria-label*='Option' i], input[placeholder*='Option' i]").all()
        option_fields = [inp for inp in all_inps if inp.is_visible()]
        print(f"🔹 Found {len(option_fields)} visible Text Poll option fields for {len(options)} options.")

        for idx, opt_text in enumerate(options):
            if idx < len(option_fields):
                print(f"🔹 Setting Text Poll Option {chr(65+idx)}: {opt_text}")
                inp = option_fields[idx]
                inp.click(force=True)
                inp.focus()
                # Clear and set value via evaluate + input event dispatch ONLY (prevents duplicate text typing)
                inp.evaluate(f"""el => {{
                    el.focus();
                    el.value = {json.dumps(opt_text)};
                    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                }}""")
                page.wait_for_timeout(300)

        print("🚀 Submitting YouTube Text Engagement Poll...")
        post_btn = composer.locator("#submit-button button, button#submit-button, button[aria-label*='Post' i], button:has-text('Post')").last
        page.wait_for_timeout(2000)
        
        if post_btn.is_visible():
            print("🚀 Clicking Post button...")
            post_btn.click(force=True)
            page.wait_for_timeout(1500)
            try:
                post_btn.evaluate("el => el.click()")
            except Exception:
                pass
        else:
            print("⚠️ Post button not visible directly inside composer, clicking fallback Post button...")
            page.locator("button:has-text('Post')").last.click(force=True)

        page.wait_for_timeout(6000)

        print("🎉 YouTube Text Engagement Poll published successfully!")
        context.close()
        return True

if __name__ == "__main__":
    post_to_youtube()
