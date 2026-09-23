import os
import sys
import json
import base64
import subprocess
from playwright.sync_api import sync_playwright

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(SCRIPT_DIR, "yt_state.json")

def extract_cookies():
    print("🚀 Launching Stealth Chrome for YouTube Studio login...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome",
            headless=False,
            ignore_default_args=["--enable-automation"],
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-first-run",
                "--no-service-autorun",
                "--password-store=basic"
            ]
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)

        print("🌐 Navigating to https://studio.youtube.com...")
        page.goto("https://studio.youtube.com")

        print("\n" + "="*60)
        print("🔑 PLEASE LOG IN TO YOUR YOUTUBE ACCOUNT IN THE OPENED CHROME WINDOW.")
        print("Once you see your YouTube Studio dashboard (OdishaExamPrep), press ENTER here.")
        print("="*60 + "\n")

        input("Press ENTER here after completing login in your browser: ")

        print("💾 Saving session cookies & state to yt_state.json...")
        context.storage_state(path=STATE_FILE)
        browser.close()

        print(f"✅ Session state successfully saved to: {STATE_FILE}")

        with open(STATE_FILE, "rb") as f:
            b64_str = base64.b64encode(f.read()).decode("utf-8")

        print("\n" + "="*70)
        print("📋 YT_STATE_BASE64 STRING (Ready for GitHub secret):")
        print("="*70)
        print(b64_str)
        print("="*70 + "\n")

        try:
            subprocess.run("clip", input=b64_str.encode("utf-8"), check=True)
            print("📋 Base64 string COPIED TO YOUR CLIPBOARD!")
        except Exception as e:
            print(f"Clipboard notice: {e}")

if __name__ == "__main__":
    extract_cookies()
