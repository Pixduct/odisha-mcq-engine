import os
from playwright.sync_api import sync_playwright

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILE_DIR = os.path.join(SCRIPT_DIR, "yt_profile")
STATE_FILE = os.path.join(SCRIPT_DIR, "yt_state.json")

with sync_playwright() as p:
    if os.path.exists(PROFILE_DIR):
        print("Launching with PROFILE_DIR...")
        context = p.chromium.launch_persistent_context(user_data_dir=PROFILE_DIR, headless=False)
        page = context.pages[0] if context.pages else context.new_page()
    else:
        print("Launching with STATE_FILE...")
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(storage_state=STATE_FILE)
        page = context.new_page()

    print("Navigating to https://www.youtube.com...")
    page.goto("https://www.youtube.com")
    page.wait_for_timeout(3000)
    print(f"Current URL: {page.url}")

    print("Navigating to https://www.youtube.com/posts...")
    page.goto("https://www.youtube.com/posts")
    page.wait_for_timeout(3000)
    print(f"Current URL: {page.url}")

    print("Navigating to https://studio.youtube.com...")
    page.goto("https://studio.youtube.com")
    page.wait_for_timeout(4000)
    print(f"Final URL: {page.url}")

    print("Press ENTER to exit...")
    input()
    context.close()
