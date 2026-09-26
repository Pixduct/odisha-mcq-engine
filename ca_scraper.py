import os
import sys
import json
import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Max age for scraped news items (48-hour authentic window — captures today & yesterday's gazette updates)
FRESHNESS_HOURS = 48
MIN_ITEMS_PER_FEED = 1

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SEEN_FILE = os.path.join(SCRIPT_DIR, "seen_ca_news.json")

RSS_FEEDS = [
    # 1. 🏛️ ODISHA STATE STREAMS (Government & Regional Authoritative Feeds)
    {
        "name": "PIB Odisha (English)",
        "url": "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3",
        "priority": "ODISHA",
        "stream": "odisha"
    },
    {
        "name": "PIB Odisha (Regional)",
        "url": "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=2&Regid=3",
        "priority": "ODISHA",
        "stream": "odisha"
    },
    {
        "name": "Odisha Bytes",
        "url": "https://odishabytes.com/feed/",
        "priority": "ODISHA",
        "stream": "odisha"
    },
    {
        "name": "Pragativadi Odisha",
        "url": "https://pragativadi.com/feed/",
        "priority": "ODISHA",
        "stream": "odisha"
    },
    {
        "name": "OrissaPOST Odisha",
        "url": "https://www.orissapost.com/feed/",
        "priority": "ODISHA",
        "stream": "odisha"
    },
    {
        "name": "Kalinga TV Odisha",
        "url": "https://kalingatv.com/feed/",
        "priority": "ODISHA",
        "stream": "odisha"
    },
    {
        "name": "Google News Odisha Governance",
        "url": "https://news.google.com/rss/search?q=Odisha+(Cabinet+OR+Scheme+OR+Yojana+OR+Government)+when:2d&hl=en-IN&gl=IN&ceid=IN:en",
        "priority": "ODISHA",
        "stream": "odisha"
    },
    
    # 2. 🇮🇳 NATIONAL GOVERNANCE, POLITY & CONSTITUTIONAL STREAMS
    {
        "name": "PIB National (English)",
        "url": "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=1",
        "priority": "NATIONAL",
        "stream": "national"
    },
    {
        "name": "The Hindu National",
        "url": "https://www.thehindu.com/news/national/feeder/default.rss",
        "priority": "NATIONAL",
        "stream": "national"
    },
    {
        "name": "Indian Express India",
        "url": "https://indianexpress.com/section/india/feed/",
        "priority": "NATIONAL",
        "stream": "national"
    },
    {
        "name": "Google News National Polity",
        "url": "https://news.google.com/rss/search?q=(Cabinet+OR+Ministry+OR+Parliament+OR+%22Supreme+Court%22+OR+%22High+Court%22)+when:2d&hl=en-IN&gl=IN&ceid=IN:en",
        "priority": "NATIONAL",
        "stream": "national"
    },
    
    # 3. 💰 ECONOMY, BANKING, TRADE & INFRASTRUCTURE STREAMS
    {
        "name": "Business Standard Economy",
        "url": "https://www.business-standard.com/rss/latest-news-101.rss",
        "priority": "NATIONAL",
        "stream": "economy"
    },
    {
        "name": "The Hindu Business & Economy",
        "url": "https://www.thehindu.com/business/Economy/feeder/default.rss",
        "priority": "NATIONAL",
        "stream": "economy"
    },
    {
        "name": "Indian Express Business",
        "url": "https://indianexpress.com/section/business/feed/",
        "priority": "NATIONAL",
        "stream": "economy"
    },
    {
        "name": "Google News Economy & RBI",
        "url": "https://news.google.com/rss/search?q=(RBI+OR+GDP+OR+Inflation+OR+Repo+Rate+OR+%22Finance+Ministry%22)+when:2d&hl=en-IN&gl=IN&ceid=IN:en",
        "priority": "NATIONAL",
        "stream": "economy"
    },
    
    # 4. 🚀 SCIENCE, SPACE, DEFENSE & DEEP TECH STREAMS
    {
        "name": "The Hindu Science",
        "url": "https://www.thehindu.com/sci-tech/science/feeder/default.rss",
        "priority": "NATIONAL",
        "stream": "science_tech"
    },
    {
        "name": "The Hindu Technology",
        "url": "https://www.thehindu.com/sci-tech/technology/feeder/default.rss",
        "priority": "NATIONAL",
        "stream": "science_tech"
    },
    {
        "name": "Indian Express Technology",
        "url": "https://indianexpress.com/section/technology/feed/",
        "priority": "NATIONAL",
        "stream": "science_tech"
    },
    {
        "name": "Google News Science & Defense",
        "url": "https://news.google.com/rss/search?q=(ISRO+OR+DRDO+OR+Missile+OR+Defence+OR+Space+OR+Satellite)+when:2d&hl=en-IN&gl=IN&ceid=IN:en",
        "priority": "NATIONAL",
        "stream": "science_tech"
    },
    
    # 5. 🏆 SPORTS MILESTONES, CHAMPIONSHIPS & AWARDS STREAMS
    {
        "name": "The Hindu Sports",
        "url": "https://www.thehindu.com/sport/feeder/default.rss",
        "priority": "NATIONAL",
        "stream": "sports"
    },
    {
        "name": "Indian Express Sports",
        "url": "https://indianexpress.com/section/sports/feed/",
        "priority": "NATIONAL",
        "stream": "sports"
    },
    {
        "name": "Google News Sports & Awards",
        "url": "https://news.google.com/rss/search?q=(Championship+OR+%22Gold+Medal%22+OR+%22Asian+Games%22+OR+%22Khel+Ratna%22+OR+Tournament)+when:2d&hl=en-IN&gl=IN&ceid=IN:en",
        "priority": "NATIONAL",
        "stream": "sports"
    },
    
    # 6. 🌿 ENVIRONMENT, ECOLOGY & CLIMATE STREAMS
    {
        "name": "The Hindu Energy & Environment",
        "url": "https://www.thehindu.com/sci-tech/energy-and-environment/feeder/default.rss",
        "priority": "NATIONAL",
        "stream": "environment"
    },
    {
        "name": "Google News Environment & Wildlife",
        "url": "https://news.google.com/rss/search?q=(%22National+Park%22+OR+%22Tiger+Reserve%22+OR+Pollution+OR+Climate+OR+Ramsar)+when:2d&hl=en-IN&gl=IN&ceid=IN:en",
        "priority": "NATIONAL",
        "stream": "environment"
    },
    
    # 7. 🌐 INTERNATIONAL RELATIONS, MULTILATERAL SUMMITS & WORLD STREAMS
    {
        "name": "The Hindu International",
        "url": "https://www.thehindu.com/news/international/feeder/default.rss",
        "priority": "WORLD",
        "stream": "world"
    },
    {
        "name": "BBC World News",
        "url": "http://feeds.bbci.co.uk/news/world/rss.xml",
        "priority": "WORLD",
        "stream": "world"
    },
    {
        "name": "Al Jazeera World",
        "url": "https://www.aljazeera.com/xml/rss/all.xml",
        "priority": "WORLD",
        "stream": "world"
    },
    {
        "name": "Google News World Diplomacy",
        "url": "https://news.google.com/rss/search?q=(Summit+OR+Treaty+OR+%22United+Nations%22+OR+BRICS+OR+G20+OR+Bilateral)+when:2d&hl=en-IN&gl=IN&ceid=IN:en",
        "priority": "WORLD",
        "stream": "world"
    }
]

def load_seen_news():
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ Error loading {SEEN_FILE}: {e}")
    return []

def save_seen_news(seen_list):
    try:
        # Keep last 300 items (approx 2 months of history)
        trimmed_list = seen_list[-300:]
        with open(SEEN_FILE, "w", encoding="utf-8") as f:
            json.dump(trimmed_list, f, indent=2, ensure_ascii=False)
        print(f"✅ Updated {SEEN_FILE} (History count: {len(trimmed_list)})")
    except Exception as e:
        print(f"⚠️ Error saving {SEEN_FILE}: {e}")

def normalize_title(title):
    import re
    return re.sub(r'[^a-zA-Z0-9]', '', title.lower())

def fetch_feed_items(feed_info):
    items = []
    url = feed_info["url"]
    name = feed_info["name"]
    priority = feed_info["priority"]
    stream = feed_info.get("stream", "general")
    
    print(f"[VERBOSE LOG] Scraping {name} RSS feed from {url}...")

    # Try using feedparser first if available
    try:
        import feedparser
        d = feedparser.parse(url)
        for entry in d.entries[:35]:
            title = getattr(entry, 'title', '').strip()
            summary = getattr(entry, 'summary', getattr(entry, 'description', '')).strip()
            if not title:
                continue
            # Extract publish date if available
            pub_date_str = ""
            pub_dt = None
            pp = getattr(entry, 'published_parsed', None) or getattr(entry, 'updated_parsed', None)
            if pp:
                try:
                    pub_dt = datetime(*pp[:6], tzinfo=timezone.utc)
                    pub_date_str = pub_dt.strftime("%Y-%m-%d")
                except Exception:
                    pass
            items.append({
                "source": name,
                "priority": priority,
                "stream": stream,
                "title": title,
                "summary": summary,
                "pub_date": pub_date_str,
                "pub_dt": pub_dt
            })
        if items:
            print(f"✅ Extracted {len(items)} items from {name} via feedparser.")
            return items
    except Exception as e:
        print(f"⚠️ feedparser attempt failed for {name}: {e}. Trying XML...")

    # Fallback to requests + XML parsing / BeautifulSoup
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        }
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status()

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(res.text, 'xml')
            if not soup.find_all('item'):
                soup = BeautifulSoup(res.text, 'html.parser')
            xml_items = soup.find_all(['item', 'entry'])
            for item in xml_items[:35]:
                title_tag = item.find('title')
                desc_tag = item.find(['description', 'summary'])
                pub_tag = item.find('pubDate') or item.find('published') or item.find('updated')
                title = title_tag.get_text(strip=True) if title_tag else ""
                summary = desc_tag.get_text(strip=True) if desc_tag else ""
                pub_date_str = ""
                pub_dt = None
                if pub_tag:
                    try:
                        from email.utils import parsedate_to_datetime
                        pub_dt = parsedate_to_datetime(pub_tag.get_text(strip=True))
                        if pub_dt.tzinfo is None:
                            pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                        pub_date_str = pub_dt.strftime("%Y-%m-%d")
                    except Exception:
                        pass
                if title:
                    items.append({
                        "source": name,
                        "priority": priority,
                        "stream": stream,
                        "title": title,
                        "summary": summary,
                        "pub_date": pub_date_str,
                        "pub_dt": pub_dt
                    })
        except Exception as ex_bs4:
            print(f"⚠️ BeautifulSoup parse error: {ex_bs4}. Trying ElementTree...")
            root = ET.fromstring(res.content)
            for channel in root.findall('channel'):
                for item in channel.findall('item'):
                    title = item.findtext('title', default='').strip()
                    summary = item.findtext('description', default='').strip()
                    pub_str = item.findtext('pubDate', default='').strip() or item.findtext('published', default='').strip() or item.findtext('updated', default='').strip()
                    pub_date_str = ""
                    pub_dt = None
                    if pub_str:
                        try:
                            from email.utils import parsedate_to_datetime
                            pub_dt = parsedate_to_datetime(pub_str)
                            if pub_dt.tzinfo is None:
                                pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                            pub_date_str = pub_dt.strftime("%Y-%m-%d")
                        except Exception:
                            pass
                    if title:
                        items.append({
                            "source": name,
                            "priority": priority,
                            "stream": stream,
                            "title": title,
                            "summary": summary,
                            "pub_date": pub_date_str,
                            "pub_dt": pub_dt
                        })

        print(f"✅ Extracted {len(items)} items from {name} via XML parser.")
    except Exception as e:
        print(f"❌ Error scraping {name}: {e}")

    return items

def scrape_current_affairs():
    seen_history = load_seen_news()
    seen_set = {normalize_title(t) for t in seen_history}

    cutoff_dt = datetime.now(timezone.utc) - timedelta(hours=FRESHNESS_HOURS)
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    all_raw_items = []
    skipped_duplicates = 0

    for feed in RSS_FEEDS:
        feed_items = fetch_feed_items(feed)
        fresh_items = []
        stale_items = []
        from ca_formatter import HARD_POLITICAL_AND_NOISE_PATTERNS, is_sovereign_exam_entity

        for item in feed_items:
            item_text = (item.get("title", "") + " " + item.get("summary", "")).lower()
            
            # GATE 1: 16-Category Threat Matrix Blacklist Purge
            if any(re.search(pat, item_text) for pat in HARD_POLITICAL_AND_NOISE_PATTERNS):
                continue

            # GATE 2: Fail-Closed Sovereign Exam Anchor (Zero-Trust Gatekeeper)
            if not is_sovereign_exam_entity(item_text):
                continue

            norm_title = normalize_title(item["title"])
            if not norm_title or norm_title in seen_set:
                skipped_duplicates += 1
                continue
            seen_set.add(norm_title)

            pub_dt = item.get("pub_dt")
            if not pub_dt:
                # RSS feed provided no parseable date; assume fresh live feed entry
                pub_dt = datetime.now(timezone.utc)
                item["pub_dt"] = pub_dt
                if not item.get("pub_date"):
                    item["pub_date"] = today_str

            if pub_dt >= cutoff_dt:
                fresh_items.append(item)
            else:
                stale_items.append(item)

        # Only add strictly verified fresh items from this feed (no unverified fallbacks)
        all_raw_items.extend(fresh_items)

    # Organize scraped items into 6 authentic competitive exam syllabus domains
    domain_buckets = {
        "odisha": [],
        "national": [],
        "economy": [],
        "science_defense": [],
        "sports": [],
        "international": []
    }

    def sort_key(item):
        dt = item.get("pub_dt")
        return dt if dt else datetime.min.replace(tzinfo=timezone.utc)
    all_raw_items.sort(key=sort_key, reverse=True)

    for item in all_raw_items:
        p = str(item.get("priority", "")).upper()
        s = str(item.get("stream", "")).lower()
        if p == "ODISHA" or s == "odisha":
            domain_buckets["odisha"].append(item)
        elif s == "economy":
            domain_buckets["economy"].append(item)
        elif s == "science_tech":
            domain_buckets["science_defense"].append(item)
        elif s == "sports":
            domain_buckets["sports"].append(item)
        elif p == "WORLD" or s == "world":
            domain_buckets["international"].append(item)
        else:
            domain_buckets["national"].append(item)

    # Multi-Domain Quorum Assembly across all 6 core exam syllabus pillars
    candidate_selection = []
    # 1. Odisha State Affairs (up to 8 fresh items)
    candidate_selection.extend(domain_buckets["odisha"][:8])
    # 2. National Governance, Constitutional & Polity (up to 8 fresh items)
    candidate_selection.extend(domain_buckets["national"][:8])
    # 3. Economy, Banking, RBI & Trade (up to 6 fresh items)
    candidate_selection.extend(domain_buckets["economy"][:6])
    # 4. Science, Space & Defense (up to 6 fresh items)
    candidate_selection.extend(domain_buckets["science_defense"][:6])
    # 5. Sports Milestones, Medals & Honors (up to 6 fresh items)
    candidate_selection.extend(domain_buckets["sports"][:6])
    # 6. International Relations & Global Summits (up to 6 fresh items)
    candidate_selection.extend(domain_buckets["international"][:6])

    fresh_count = sum(1 for i in all_raw_items if i.get("pub_dt") and i["pub_dt"] >= cutoff_dt)
    print(f"\n✅ Total Raw News Items Scraped: {len(all_raw_items)} "
          f"({fresh_count} fresh within 48h, {skipped_duplicates} duplicates skipped)")
    print(f"📦 Unified Domain Payload: {len(candidate_selection)} candidate items across 6 core domains "
          f"(Odisha: {len(domain_buckets['odisha'][:8])}, National: {len(domain_buckets['national'][:8])}, "
          f"Economy: {len(domain_buckets['economy'][:6])}, Science/Defense: {len(domain_buckets['science_defense'][:6])}, "
          f"Sports: {len(domain_buckets['sports'][:6])}, International: {len(domain_buckets['international'][:6])})")

    formatted_text_lines = []
    for idx, item in enumerate(candidate_selection, start=1):
        pub_label = item.get("pub_date", "UNVERIFIED")
        domain_label = item.get("stream", item.get("priority", "NATIONAL")).upper()
        formatted_text_lines.append(
            f"[{idx}] Domain: {domain_label} | Source: {item['source']} | Published: {pub_label}\n"
            f"Title: {item['title']}\n"
            f"Summary: {item['summary']}\n"
        )

    raw_text_payload = "\n".join(formatted_text_lines)
    return all_raw_items, raw_text_payload

def scrape_all_feeds():
    """
    Backward-compatible helper function returning scraped raw news items list.
    """
    items, _ = scrape_current_affairs()
    return items

if __name__ == "__main__":
    items, payload = scrape_current_affairs()
    print("--- SAMPLE PAYLOAD PREVIEW ---")
    print(payload[:1000])
