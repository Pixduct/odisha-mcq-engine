import os
import sys
import json
import base64
import subprocess
import time
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILE_DIR = os.path.join(SCRIPT_DIR, "yt_profile")
STATE_FILE = os.path.join(SCRIPT_DIR, "yt_state.json")

def extract_cookies():
    print("=================================================================")
    print("🚀 AUTOMATED YOUTUBE SESSION REFRESH TOOL")
    print("=================================================================")
    print("1. A Google Chrome window will open on your screen.")
    print("2. Please log into your Google Account (OdishaExamPrep).")
    print("3. As soon as YouTube Studio loads, this tool will automatically:")
    print("   • Capture your fresh authentication cookies")
    print("   • Save them locally to yt_state.json and yt_profile")
    print("   • Automatically upload the new secret to GitHub Actions (Pixduct/odisha-mcq-engine)")
    print("=================================================================\n")

    with sync_playwright() as p:
        try:
            context = p.chromium.launch_persistent_context(
                user_data_dir=PROFILE_DIR,
                channel="chrome",
                headless=False,
                ignore_default_args=["--enable-automation"],
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-first-run",
                    "--no-service-autorun"
                ],
                viewport={"width": 1280, "height": 850}
            )
        except Exception:
            # Fallback if system Chrome is not installed in standard path
            context = p.chromium.launch_persistent_context(
                user_data_dir=PROFILE_DIR,
                headless=False,
                ignore_default_args=["--enable-automation"],
                args=["--disable-blink-features=AutomationControlled"],
                viewport={"width": 1280, "height": 850}
            )

        page = context.pages[0] if context.pages else context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        print("🌐 Opening https://studio.youtube.com ...")
        page.goto("https://studio.youtube.com")

        print("⏳ Waiting for you to complete sign-in in the Chrome window...")
        logged_in = False

        # Monitor for up to 5 minutes (300 iterations)
        for i in range(300):
            try:
                curr_url = page.url.lower()
                is_google_login = "accounts.google.com" in curr_url or "signin" in curr_url

                if not is_google_login and ("studio.youtube.com" in curr_url or "youtube.com" in curr_url):
                    # Check for logged-in avatar or studio navigation bar
                    has_avatar = page.locator("button#avatar-btn, ytcp-app, #channel-title, #entity-name").count() > 0
                    if has_avatar or ("channel" in curr_url and "studio.youtube.com" in curr_url):
                        print("\n🎉 YouTube Studio authenticated session detected!")
                        page.wait_for_timeout(3000)
                        logged_in = True
                        break
            except Exception:
                # Browser might be closed by user
                break

            time.sleep(1)

        print("\n💾 Capturing session cookies & storage state...")
        context.storage_state(path=STATE_FILE)
        context.close()

        if not os.path.exists(STATE_FILE):
            print("❌ Error: Failed to save storage state file.")
            return False

        print(f"✅ Session state successfully saved to: {STATE_FILE}")

        with open(STATE_FILE, "rb") as f:
            b64_str = base64.b64encode(f.read()).decode("utf-8")

        # Copy to clipboard
        try:
            subprocess.run("clip", input=b64_str.encode("utf-8"), check=True)
            print("📋 Base64 string automatically copied to your clipboard!")
        except Exception:
            pass

        # Automatically update GitHub Secrets via gh CLI
        print("☁️ Automatically uploading updated session secrets to GitHub Actions...")
        try:
            res1 = subprocess.run(
                ["gh", "secret", "set", "YT_STATE_BASE64", "-b", b64_str, "--repo", "Pixduct/odisha-mcq-engine"],
                capture_output=True,
                text=True
            )
            res2 = subprocess.run(
                ["gh", "secret", "set", "YOUTUBE_STORAGE_STATE", "-b", b64_str, "--repo", "Pixduct/odisha-mcq-engine"],
                capture_output=True,
                text=True
            )
            if res1.returncode == 0 and res2.returncode == 0:
                print("🚀 GitHub Secrets (YT_STATE_BASE64 & YOUTUBE_STORAGE_STATE) successfully updated in Pixduct/odisha-mcq-engine!")
            else:
                print(f"⚠️ Note on GitHub secret upload: {res1.stderr or res2.stderr}")
        except Exception as ex_gh:
            print(f"⚠️ Notice updating GitHub secrets: {ex_gh}")

        print("\n=================================================================")
        print("✅ YOUTUBE SESSION REFRESH COMPLETE!")
        print("Your automations are now fully authenticated to post image carousels.")
        print("=================================================================\n")
        return True

if __name__ == "__main__":
    extract_cookies()
