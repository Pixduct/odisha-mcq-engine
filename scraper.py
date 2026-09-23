import os
import sys
import json
import hashlib
import requests
import urllib3
from bs4 import BeautifulSoup
from datetime import datetime

# Suppress SSL InsecureRequestWarning for government portals
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SEEN_NOTICES_FILE = os.path.join(SCRIPT_DIR, "seen_notices.json")
WEBHOOK_URL = os.getenv("BREAKING_WEBHOOK_URL") or "https://odisha-mcq-engine.onrender.com/webhook/breaking-notice"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache"
}

def load_seen_notices():
    if os.path.exists(SEEN_NOTICES_FILE):
        try:
            with open(SEEN_NOTICES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Error reading {SEEN_NOTICES_FILE}: {e}")
    return {}

def save_seen_notices(seen_dict):
    try:
        with open(SEEN_NOTICES_FILE, "w", encoding="utf-8") as f:
            json.dump(seen_dict, f, indent=2, ensure_ascii=False)
        print(f"💾 Updated {SEEN_NOTICES_FILE} with {len(seen_dict)} total recorded notices.")
    except Exception as e:
        print(f"❌ Error saving {SEEN_NOTICES_FILE}: {e}")

def get_notice_hash(portal_name, title, link):
    key = f"{portal_name.upper()}:{title.strip().lower()}:{link.strip()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()

def fetch_page_content(url):
    try:
        res = requests.get(url, headers=HEADERS, timeout=25, verify=False)
        if res.ok:
            return res.text
        else:
            print(f"⚠️ HTTP {res.status_code} fetching {url}")
    except Exception as e:
        print(f"⚠️ Request exception for {url}: {e}")
    return ""

def parse_generic_portal(url, portal_name, min_text_len=8):
    print(f"[VERBOSE LOG] Scraping official notification feed for {portal_name} ({url})...")
    html = fetch_page_content(url)
    if not html:
        print(f"⚠️ Empty response from {portal_name}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    
    # Strip non-content header, footer, navigation, and script elements
    for element in soup(["header", "footer", "nav", "script", "style", "iframe"]):
        element.extract()

    items = []

    # Strategy 1: Targeted notification containers (Tables, Lists, News Sections)
    notice_containers = soup.find_all(
        ["table", "ul", "ol", "tbody", "div", "section"],
        class_=lambda c: c and any(k in str(c).lower() for k in ["notice", "notification", "what-new", "whatsnew", "latest", "update", "announcement", "news", "grid", "gdv"])
    )

    candidate_rows = []
    if notice_containers:
        for nc in notice_containers:
            candidate_rows.extend(nc.find_all(["tr", "li", "article"]))
    
    if not candidate_rows:
        candidate_rows = soup.find_all(["tr", "li"])

    ignored_keywords = [
        "home", "contact", "about", "login", "privacy", "terms", "sitemap", 
        "disclaimer", "back", "next", "previous", "faq", "gallery", "tender", 
        "rti", "feedback", "copyright", "help", "register", "download app", "sign in", "skip",
        "national portal of india", "india.gov.in", "national portal", "india portal",
        "accessibility statement", "website policy", "hyperlinking policy", "copyright policy",
        "class ix", "class 9", "class 8", "annual class ix", "madhyama examination", "high school certificate"
    ]

    for row in candidate_rows:
        a_tag = row.find("a")
        if a_tag:
            if not href or href in ["#", "javascript:void(0);", "javascript:void(0)", "javascript:;"]:
                continue

            if href.lower().startswith("javascript:"):
                full_link = url
            else:
                full_link = href if href.startswith("http") else requests.compat.urljoin(url, href)

            if len(title) >= min_text_len and not any(ik in title.lower() for ik in ignored_keywords):
                c_text = row.get_text(" ", strip=True)
                items.append({
                    "portal": portal_name,
                    "title": title,
                    "link": full_link,
                    "full_text": c_text
                })

    # Strategy 2: Direct links fallback within page body
    if not items:
        for a_tag in soup.find_all("a"):
            title = a_tag.get_text(" ", strip=True)
            href = a_tag.get("href", "").strip()
            if not href or href in ["#", "javascript:void(0);", "javascript:void(0)"]:
                continue
            if len(title) >= min_text_len and not any(ik in title.lower() for ik in ignored_keywords):
                full_link = href if href.startswith("http") else requests.compat.urljoin(url, href)
                items.append({
                    "portal": portal_name,
                    "title": title,
                    "link": full_link,
                    "full_text": title
                })

    # Deduplicate items in current scrape batch by title
    unique_items = []
    seen_batch_titles = set()
    for item in items:
        clean_t = item["title"].lower()
        if clean_t not in seen_batch_titles:
            seen_batch_titles.add(clean_t)
            unique_items.append(item)

    print(f"✅ Extracted {len(unique_items)} official notification items from {portal_name}.")
    return unique_items[:15]  # Top 15 items per portal

def fetch_deep_notice_content(url):
    if not url or not url.startswith("http") or url.lower().endswith(".pdf"):
        return ""
    try:
        print(f"🔍 Deep-scraping notice page context: {url}...")
        html = fetch_page_content(url)
        if not html:
            return ""
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.extract()
        main_content = soup.find(["main", "article", "div"], class_=lambda c: c and any(k in str(c).lower() for k in ["content", "main", "body", "detail", "notice"]))
        if not main_content:
            main_content = soup.body
        if main_content:
            text = main_content.get_text("\n", strip=True)
            cleaned_text = "\n".join([line.strip() for line in text.split("\n") if len(line.strip()) > 10])
            return cleaned_text[:3500]
    except Exception as e:
        print(f"⚠️ Deep scrape note for {url}: {e}")
    return ""

def post_breaking_notice_webhook(portal_name, title, link, details=""):
    print(f"📢 Processing breaking notice for [{portal_name}] {title[:50]}...")
    
    deep_content = fetch_deep_notice_content(link)
    combined_details = f"{details}\n{deep_content}".strip() if deep_content else details

    notice_text = f"[{portal_name}] {title}\nOfficial Link: {link}"
    if combined_details and combined_details != title:
        notice_text += f"\nDetails:\n{combined_details[:3500]}"

    # Try direct processing in GitHub Actions environment (has Playwright & YT session)
    try:
        import breaking_engine
        print(f"🚀 Launching direct Breaking Alert Engine for [{portal_name}] notice...")
        breaking_engine.process_breaking_notice_direct(notice_text, link_url=link)
        return True
    except Exception as direct_err:
        print(f"⚠️ Direct processing note ({direct_err}). Sending to fallback webhook endpoint...")

    payload = {"notice_text": notice_text, "link": link}
    try:
        res = requests.post(WEBHOOK_URL, json=payload, timeout=30)
        if res.ok:
            print(f"✅ Successfully posted [{portal_name}] notice to webhook!")
            return True
        else:
            print(f"⚠️ Webhook response HTTP {res.status_code}: {res.text}")
    except Exception as e:
        print(f"❌ Webhook request failed: {e}")
    return False

def check_already_published_in_supabase(title: str) -> bool:
    try:
        from shared.supabase_client import SupabaseBlogClient
        client = SupabaseBlogClient()
        existing = client.fetch_all_blogs()
        norm_title = title.lower().strip()
        for b in existing:
            name = str(b.get("name", "")).lower().strip()
            if name and (name == norm_title or norm_title in name or name in norm_title):
                return True
    except Exception:
        pass
    return False

def scrape_all_portals():
    print("==================================================")
    print("🔍 RECRUITMENT PORTAL NOTICE SCRAPER ENGINE")
    print("==================================================\n")

    portals = [
        ("OPSC", "https://www.opsc.gov.in/Public/Pages/Notices.aspx"),
        ("OSSC", "https://www.ossc.gov.in/Public/Pages/What_is_new.aspx"),
        ("OSSSC", "https://www.osssc.gov.in/Public/Notifications.aspx"),
        ("BSE Odisha", "http://bseodisha.ac.in/latest-updates.html"),
        ("SSC Central", "https://ssc.gov.in/"),
        ("UPSC Central", "https://upsc.gov.in/whats-new"),
        ("IBPS Banking", "https://www.ibps.in/"),
        ("RRB Bhubaneswar", "https://rrbbbs.gov.in/"),
        ("NTA Exams", "https://nta.ac.in/Notice")
    ]

    seen_records = load_seen_notices()
    new_notices_count = 0

    for portal_name, url in portals:
        try:
            items = parse_generic_portal(url, portal_name)
            for item in items:
                title = item["title"]
                link = item["link"]
                details = item.get("full_text", "")
                
                notice_hash = get_notice_hash(portal_name, title, link)

                if notice_hash not in seen_records and not check_already_published_in_supabase(title):
                    print(f"🚨 NEW NOTICE DETECTED: [{portal_name}] {title}")
                    
                    # Dispatch to webhook
                    web_success = post_breaking_notice_webhook(portal_name, title, link, details)
                    
                    # Record in seen_notices.json
                    seen_records[notice_hash] = {
                        "portal": portal_name,
                        "title": title,
                        "link": link,
                        "first_seen": datetime.now().isoformat()
                    }
                    new_notices_count += 1
                else:
                    print(f"ℹ️ [Notice Scraper] Notice already processed/published: [{portal_name}] {title[:40]}... Skipping.")

        except Exception as e:
            print(f"❌ Error scraping {portal_name}: {e}")

    save_seen_notices(seen_records)
    print(f"\n🎉 Scraper run complete! {new_notices_count} new breaking notices processed.")

    if new_notices_count > 0:
        try:
            from shared.telegram import send_admin_alert
            summary_msg = (
                f"🚨 <b>Recruitment Notice Scraper Execution Summary</b>\n\n"
                f"📅 <b>Date:</b> {datetime.now().strftime('%d %B %Y %I:%M %p')}\n"
                f"🏛️ <b>Portals Scanned:</b> {len(portals)} master recruitment portals\n"
                f"⚡ <b>New Breaking Notices Processed:</b> {new_notices_count}\n"
                f"✅ Webhooks & database updates dispatched."
            )
            send_admin_alert("NOTICE_SCRAPER", "SUCCESS", {"message": summary_msg})
        except Exception as alert_err:
            print(f"⚠️ Notice Scraper Admin Alert notice: {alert_err}")

if __name__ == "__main__":
    scrape_all_portals()
