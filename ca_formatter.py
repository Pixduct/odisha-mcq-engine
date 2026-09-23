import os
import sys
import json
import re
import requests
from datetime import datetime
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
from ca_scraper import load_seen_news, save_seen_news, normalize_title

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

DEEPSEEK_API_KEY = (
    os.getenv("DEEPSEEK_API_KEY") or
    os.getenv("NVIDIA_NIM_API_KEY") or
    os.getenv("OPENAI_API_KEY") or
    os.getenv("VITE_DEEPSEEK_API_KEY") or
    ""
).strip('"')

DEEPSEEK_BASE_URL = (
    os.getenv("DEEPSEEK_BASE_URL") or
    os.getenv("VITE_DEEPSEEK_BASE_URL") or
    "https://integrate.api.nvidia.com/v1"
).strip('"')

# Module-level AI model tracking — read by ca_publisher.py for admin Telegram report
_ca_ai_model_used = "nvidia/nemotron-3-super-120b-a12b"
_ca_ai_used_fallback = False

# 15-CATEGORY NON-EXAM THREAT MODEL MATRIX & NOISE BLACKLIST PATTERNS
HARD_POLITICAL_AND_NOISE_PATTERNS = [
    # 1. Op-Eds, Columns, Editorial Essays & Philosophical Musings (Zero Concrete Exam GK Facts)
    r'\b(?:column\s*\||in\s+screenshots\s+we\s+trust|opinion\s*\||editorial\s*\||in\s+perspective\s*\||first\s+person\s*\||essay\s*\||personal\s+finance\s*\||my\s+take\s*\||view\s*:|the\s+big\s+interview\s*:|why\s+we\s+love|why\s+we\s+need|letter\s+to\s+the\s+editor|book\s+review)\b',

    # 2. Commercial Consumer Electronics, Smartphones, Wearables & Gadget Specs (Zero Exam GK)
    r'\b(?:samsung\s+(?:galaxy|expected|launches|unveils)|galaxy\s+s\d+|galaxy\s+z|galaxy\s+a\d+|galaxy\s+event|galaxy\s+s\d+\s+fe|redmi\s+(?:watch|note|phone|k\d+|smartwatch)|xiaomi|realme|oppo|vivo|oneplus|iqoo|motorola|infinix|techno|smartwatch|smart\s+watch|fitness\s+tracker|amoled\s+display|refresh\s+rate|battery\s+life|cny\s+\d+|mah\s+battery|fast\s+charging|45w\s+charger|snapdragon|mediatek|earbuds|tws|headset|flagship\s+phone|smart\s+tv|unboxing|leaked\s+specs|first\s+look|foldable\s+phone|poco\s+launches)\b',

    # 3. Private Corporate Leadership, FMCG Board Appointments & Private Company Management
    r'\b(?:colgate|palmolive|kenvue|unilever|hul\b|nestle|pepsico|coca-cola|swiggy|zomato|paytm|ola\s+electric|uber|flipkart|amazon\s+india|byju|infosys|wipro|tcs\b|tata\s+motors|mahindra|reliance\s+retail|dmart|nykaa)\s+(?:appoints|names|elevates|ropes\s+in|managing\s+director|ceo|cfo|coo|leadership\s+change|to\s+lead|moves\s+to\s+apac)\b',
    r'\b(?:lead\s+colgate|managing\s+director\s+of\s+colgate|ceo\s+of\s+colgate|prabha\s+narasimhan|manish\s+anandani)\b',

    # 4. Private Corporate Quarterly Earnings, Financial Margins & Stock Market Ticker Gossip
    r'\b(?:q[1-4]\s+net\s+profit|quarterly\s+net\s+profit|q[1-4]\s+results|quarterly\s+revenue|ebitda\s+margin|interim\s+dividend\s+of\s+₹|share\s+price\s+(?:surges|slumps|rallies|dips)|sensex\s+(?:gains|falls|rallies|plunges)|nifty\s+(?:crosses|slips|closes)|gold\s+prices?\s+(?:hit|rise|drop)|bullion\s+market|crude\s+oil\s+futures)\b',

    # 5. Ceremonial / Condolence / Protocol Visits (Sovereign Name Hijack Blocker)
    r'\b(?:condolences?\s+on\s+death|offers?\s+condolences?|mourns?\s+demise|greets?\s+people\s+on|wishes?\s+citizens|inaugurates?\s+annual\s+sports\s+meet\s+of\s+school|attends?\s+family\s+function|temple\s+darshan|performs?\s+puja|offers?\s+prayers\s+at|pays?\s+floral\s+tributes?|lays?\s+wreath\s+at)\b',

    # 6. Routine Local Police Crime, Contraband Seizures & Petty Bribery
    r'\b(?:ganja\s+seized|smuggled\s+liquor|illicit\s+liquor|cyber\s+fraud\s+gang|vigilance\s+trap|vigilance\s+catches|caught\s+red-handed\s+taking\s+bribe|junior\s+engineer\s+arrested|bribe\s+of\s+₹|illegal\s+sand\s+mining\s+trucks?|poachers?\s+held|counterfeit\s+currency\s+seized)\b',

    # 7. Minor Civic Maintenance & Municipal Micro-Tariffs
    r'\b(?:parking\s+fee(?:s)?|panchayat\s+parking|lsgd\s+revises|minimum\s+parking|auto\s+fare|taxi\s+fare|bus\s+fare|toll\s+rates\s+revised|metro\s+ticket\s+price|water\s+tariff|electricity\s+tariff\s+hike|power\s+bill\s+revision|building\s+permit\s+fee|waste\s+collection\s+charge)\b',
    r'\b(?:pothole\s+repair|road\s+repair\s+work|water\s+pipe\s+leakage|water\s+supply\s+disrupted|streetlights?\s+installed|garbage\s+cleaning\s+drive|drainage\s+cleaning|clearing\s+encroachments?|demolition\s+drive\s+by\s+civic)\b',

    # 8. Sports Injury / Match Commentary / Press Conference Gossip
    r'\b(?:ruled\s+out\s+due\s+to\s+injury|hamstring\s+injury|praises?\s+team\s+spirit|press\s+conference\s+ahead\s+of|toss\s+delayed|franchise\s+signs\s+new\s+coach|captain\s+says\s+we\s+need|post-match\s+presentation|dressing\s+room\s+chatter)\b',

    # 9. Internal Academic Administration & Exam Rescheduling Routine
    r'\b(?:postpones?\s+(?:[0-9a-z]+\s+)?semester\s+exam|semester\s+exam\s+postponed|semester\s+exam\s+dates?\s+revised|college\s+holiday\s+declared|alumni\s+meet\s+held|annual\s+day\s+function|college\s+fest|convocation\s+rehearsal)\b',

    # 10. Political Agitations, Dharnas, Gherao & Sloganeering
    r'\b(?:dharna|sit-in|protest\s+at\s+police|sloganeering|raising\s+slogans|party\s+workers|barricaded\s+the\s+area)\b',
    r'\b(?:rapid\s+action\s+force\s+was\s+called|staged\s+a\s+sit-dharna|staged\s+a\s+dharna|staged\s+a\s+protest)\b',
    r'\b(?:police\s+station\s+protest|gherao|court\s+arrest|traffic\s+blockade)\b',
    
    # 11. Political Speeches, Rally Rhetoric, Verbal Statements & Mudslinging (NOT actual policy or acts)
    r'\b(?:criticized\s+previous|slammed|lashed\s+out|attacked\s+(?:the\s+)?opposition|gave\s+out\s+wrong\s+signals)\b',
    r'\b(?:hit\s+out\s+at|political\s+mudslinging|election\s+campaign\s+rhetoric|speech\s+at\s+rally|addressing\s+party\s+workers)\b',
    r'\b(?:slammed\s+the\s+police|mute\s+spectator)\b',
    r'\b(?:will\s+not\s+be\s+safe\s+until|won\'t\s+be\s+safe\s+till|borders?\s+are\s+secure|has\s+stated\s+that|stated\s+that\s+india|emphasized\s+the\s+importance\s+of|highlighted\s+the\s+need|urged\s+(?:citizens|people|officials)|called\s+upon|appealed\s+to|advised\s+party|warned\s+that|cautioned\s+against|addressed\s+a\s+gathering|speaking\s+at\s+the\s+inauguration|speech\s+at\s+the|said\s+while\s+addressing|expressed\s+confidence\s+that|reiterated\s+commitment|hailed\s+the\s+role\s+of)\b',
    
    # 12. Private Corporate Pricing & Commercial Product Price Changes (Zero Exam Value)
    r'\b(?:raise(?:s)?\s+car\s+prices|car\s+prices|suv\s+prices|hike(?:s)?\s+vehicle\s+prices|automobile\s+prices|airfare\s+hike|flight\s+ticket\s+prices|hotel\s+rates|cinema\s+ticket|cement\s+prices|steel\s+prices\s+raised\s+by|fmcg\s+prices|consumer\s+goods\s+price\s+hike)\b',
    
    # 13. Routine Meeting Frequency & Administrative Review Circulars (Lacking Concrete Outlay/Scheme)
    r'\b(?:cabinet\s+to\s+meet\s+twice|meeting\s+schedule|review\s+meeting\s+held|chaired\s+a\s+review\s+meeting|instructs\s+officials\s+to\s+speed\s+up|orders\s+timely\s+completion|urges\s+officers\s+to|meeting\s+convened\s+to\s+discuss)\b',

    # 14. Local Clashes, Confrontations & Village Disputes
    r'\b(?:villagers\s+clash|villagers\s+clashed|mob\s+clash|school\s+clash|stone\s+pelting|group\s+clash|confrontation\s+with\s+local)\b',
    
    # 15. Lifestyle, Gossip, Commercial Cinema & Minor Routine Incidents
    r'\b(?:dharma\s+productions|dharmatic|karan\s+johar|film\s+producer|film\s+production|box\s+office|celebrity\s+tax)\b',
    r'\bmovie\b', r'\bactor\b', r'\bactress\b', r'\bbollywood\b', r'\bhollywood\b', r'\bott release\b',
    r'\bcelebrity\b', r'\btheft(?:s)?\b', r'\bheist\b', r'\bteen(?:s)?\b', r'\bjuvenile(?:s)?\b',
    r'\bheld for\b', r'\bbody found\b', r'\blocal police\b', r'\bshop inauguration\b', r'\bresort\b',
    r'\bviral video\b', r'\bastrology\b', r'\brumor\b', r'\bhandwritten notes\b', r'\bed raid\b',
    r'\binterim seizure\b', r'\bvegan diet\b', r'\blifestyle study\b',
    r'\bmissing\s+(?:hiker|teen|person|girl|boy|child)\b', r'\bhiker\b', r'\bsearch\s+operation\s+for\s+missing\b',
    r'\bfound\s+dead\b', r'\bdrowned\b', r'\bbus\s+crash\b', r'\bcar\s+crash\b', r'\broad\s+accident\b',
    r'\bcampus\s+protest\b', r'\buniversity\s+protest\b', r'\bstudent\s+protest\b', r'\bstudent\s+strike\b',
    r'\bhunger\s+strike\b', r'\bcaste\s+discrimination\s+allegation\b',
    r'\b(?:dead\s+body|cremation\s+denied|funeral\s+denied|ostraciz(?:ed|ation))\b',
    # 16. Local Crime, Sexual Assault, Theft, Robbery, Cheating, Murder, Police Arrests & Accused in Custody (Zero Exam Value)
    r'\b(?:stolen|robbery|looting|burglar(?:y)?|theft|pickpocketing|snatching|smuggling|contraband|robbed\s+articles)\b',
    r'\b(?:sexual\s+assault|rape\s+case|molestation|eve\s+teasing|pocso|harassment\s+case|cheating\s+woman|pretext\s+of\s+marriage|temple\s+marriage|fake\s+marriage)\b',
    r'\b(?:arrested\s+for|arrested\s+by|arrested\s+in|held\s+with\s+stolen|held\s+for|police\s+custody|remanded\s+to\s+custody|accused\s+arrested|duo\s+held|gang\s+busted|police\s+have\s+recovered|currently\s+in\s+custody|sent\s+to\s+jail|sent\s+to\s+judicial\s+custody|registered\s+a\s+rape\s+case|registered\s+a\s+case\s+against)\b',
    r'\b(?:murder\s+case|killed\s+over|stabbed\s+to\s+death|homicide|body\s+recovered|corpse|found\s+hanging|suicide\s+note|poisoned|strangled)\b',
    r'\b(?:sub-inspector\s+arrested|si\s+arrested|constable\s+arrested|cop\s+arrested|inspector\s+arrested|police\s+officer\s+arrested|vigilance\s+trap|bribe\s+taking|arrested\s+by\s+police|arrested\s+by\s+town\s+police)\b',
    r'\b(?:accused\s+named|native\s+of\s+[a-z]+|befriended\s+the\s+victim|separated\s+from\s+husband|victim\s+alleged|accused\s+has\s+been)\b'
]

def truncate_word_safe(text, max_len=135):
    text = text.strip()
    if len(text) <= max_len:
        return text
    truncated = text[:max_len]
    if " " in truncated:
        truncated = truncated.rsplit(" ", 1)[0]
    return truncated.rstrip(",.- ") + "..."

def highlight_keypoint_label(text):
    text = text.strip()
    if "<b>" in text and "</b>" in text:
        return text
    
    if ":" in text:
        parts = text.split(":", 1)
        label = parts[0].strip()
        val = parts[1].strip()
        return f"<b>{label}:</b> {val}"
    
    return text

def significant_words(text):
    """Extract meaningful 4+ char words, excluding common stop words."""
    import re
    words = set(re.findall(r'\b[a-zA-Z]{4,}\b', text.lower()))
    stop = {'with','from','that','this','have','been','will','also','more',
            'into','over','under','after','about','their','they','which',
            'were','when','then','than','your','news','today','india'}
    return words - stop


def verify_slide_dates(slides, raw_text_payload, today_iso, yesterday_iso):
    """
    Cross-references each AI slide headline against the 'Published:' dates
    in the raw scraper payload within the 48-hour authentic window.
    """
    import re
    from datetime import datetime, timedelta
    
    # Allow 48-hour breaking & gazette current affairs (TODAY, YESTERDAY, 2-DAYS AGO)
    try:
        t_dt = datetime.strptime(today_iso, "%Y-%m-%d")
        valid_dates = {
            today_iso,
            yesterday_iso,
            (t_dt - timedelta(days=2)).strftime("%Y-%m-%d")
        }
    except Exception:
        valid_dates = {today_iso, yesterday_iso}

    # Extract all (pub_date, title) pairs from raw payload
    raw_articles = re.findall(
        r'\| Published: (\S+)\nTitle: (.+)',
        raw_text_payload
    )

    verified, dropped = [], []

    for slide in slides:
        headline = slide.get("headline", "")
        h_words = significant_words(headline)

        if len(h_words) < 2:
            # Too short to match — keep with no penalty
            verified.append(slide)
            continue

        # Find best keyword-overlap match in raw payload
        best_overlap, best_pub_date = 0, None
        for pub_date, title in raw_articles:
            overlap = len(h_words & significant_words(title))
            if overlap > best_overlap:
                best_overlap, best_pub_date = overlap, pub_date

        if best_overlap >= 2 and best_pub_date and best_pub_date != "UNVERIFIED" and best_pub_date not in valid_dates:
            # Matched a source article but it's older than 48h — DROP
            reason = f"source dated {best_pub_date}"
            dropped.append(f"'{headline[:55]}' ({reason})")
            print(f"⚫ DATE VERIFICATION FAILED — Dropping: '{headline[:55]}' | {reason}")
        else:
            verified.append(slide)

    if dropped:
        print(f"\n⚫ Verification summary: dropped {len(dropped)} stale slide(s):")
        for d in dropped:
            print(f"   • {d}")
    else:
        print(f"✅ Date verification passed: all {len(slides)} slide(s) are fresh.")

    return verified, dropped


def sanitize_zero_truncation(text: str) -> str:
    """
    Absolute Zero Truncation Sanitizer (NO '...').
    Removes trailing ellipses, truncated sentence fragments, and guarantees fully expressed, complete sentences.
    """
    if not text:
        return ""
    
    clean = str(text).strip()
    
    # Strip trailing ellipses (... or .. or …)
    while clean.endswith("...") or clean.endswith("..") or clean.endswith("…"):
        clean = re.sub(r'[\.\s\…]+$', '', clean).strip()
    
    # If mid-sentence cut off without closing period, ensure clean closing period
    if clean and not clean.endswith(('.', '!', '?')):
        clean += "."
    
    return clean

def classify_news_category(headline: str, bullets: list = None, raw_category: str = "") -> str:
    """
    Dynamic Syllabus Micro-Tag & Category Auto-Correction Engine for Odisha and Central Exams.
    Accurately assigns syllabus domain badges without ever dropping valid exam news.
    """
    import re
    text = f"{headline} " + " ".join(bullets if isinstance(bullets, list) else [])
    t_lower = text.lower()

    # 1. SPORTS (Must have genuine sports terms)
    SPORTS_KW = [
        'cricket', 'test match', 'test journey', 'test series', 'run win', 'wicket', 'stadium', 'olympic', 'world cup',
        'badminton', 'tennis', 'football', 'soccer', 'hockey', 'gold medal', 'silver medal', 'bronze medal',
        'grand slam', 'chess', 'fide', 'bcci', 'fifa', 'icc', 'wimbledon', 'ipl', 'athlete', 'championship',
        'trophy', 'tournament', 'medalist', 'sports', 'shuttler', 'grandmaster', 'khel ratna', 'arjuna award',
        'asian games', 'commonwealth', 'title winner', 'archery', 'boxing', 'wrestling', 'sprint', 'race'
    ]
    has_sports = any(kw in t_lower for kw in SPORTS_KW)

    # 2. ODISHA STATE AFFAIRS
    ODISHA_KW = [
        'odisha', 'bhubaneswar', 'cuttack', 'puri', 'opsc', 'ossc', 'osssc', 'opprb', 'majhi', 'naveen',
        'sambalpur', 'balasore', 'koraput', 'ganjam', 'rourkela', 'chilika', 'hirakud', 'similipal', 'malkangiri',
        'subhadra', 'mission shakti', 'bsky', 'kalia', 'srimandir', 'ekamra', 'samalei'
    ]
    has_odisha = any(kw in t_lower for kw in ODISHA_KW)

    # 3. SCIENCE, SPACE & DEFENSE
    SCI_KW = [
        'isro', 'nasa', 'satellite', 'rocket', 'ai ', 'artificial intelligence', 'quantum', 'biotech',
        'cybersecurity', 'defense tech', 'missile', 'drdo', 'invention', 'tech discovery', 'space research',
        'spacecraft', 'lunar', 'solar mission', 'supercomputer', 'semiconductor', 'nuclear reactor', 'ins '
    ]
    has_science = any(kw in t_lower for kw in SCI_KW)

    # 4. ECONOMY, BANKING & TRADE
    ECON_KW = [
        'rbi', 'reserve bank', 'gdp', 'inflation', 'gst', 'sebi', 'stock market', 'sensex', 'nifty',
        'fiscal', 'repo rate', 'banking', 'bank', 'merger', 'monetary', 'corporate finance', 'union budget',
        'trade deficit', 'forex', 'fdi', 'export', 'import', 'monetary policy'
    ]
    has_economy = any(kw in t_lower for kw in ECON_KW)

    # 5. ENVIRONMENT & ECOLOGY
    ENV_KW = [
        'pollution', 'climate change', 'wildlife', 'national park', 'sanctuary', 'biodiversity',
        'ramsar', 'tiger reserve', 'cyclone', 'earthquake', 'ecological', 'environment', 'forest',
        'iucn', 'species', 'carbon emission', 'wetland', 'conservation'
    ]
    has_env = any(kw in t_lower for kw in ENV_KW)

    # 6. ART, CULTURE & HERITAGE
    CULTURE_KW = [
        'gi tag', 'geographical indication', 'unesco', 'world heritage', 'sahitya akademi',
        'jnanpith', 'padma vibhushan', 'padma bhushan', 'padma shri', 'nobel prize', 'archaeological',
        'excavation', 'temple heritage', 'classical dance', 'folk art'
    ]
    has_culture = any(kw in t_lower for kw in CULTURE_KW)

    # 7. INTERNATIONAL RELATIONS
    INTL_KW = [
        'unsc', 'united nations', 'g20', 'g7', 'asean', 'brics', 'quad', 'nato', 'who', 'wto',
        'bilateral', 'envoy', 'ambassador', 'diplomatic', 'foreign minister', 'geopolitics',
        'world news', 'foreign policy', 'international relations', 'summit'
    ]
    has_intl = any(kw in t_lower for kw in INTL_KW)

    # 8. NATIONAL POLITY & GOVERNANCE
    GOV_KW = [
        'central government', 'union cabinet', 'pm modi', 'scheme', 'yojana', 'parliament',
        'lok sabha', 'rajya sabha', 'ministry', 'national', 'governance', 'welfare',
        'supreme court', 'high court', 'election commission', 'cag', 'niti aayog', 'bill passed', 'act notified'
    ]
    has_gov = any(kw in t_lower for kw in GOV_KW)

    # Resolve optimal category tag
    raw_clean = str(raw_category or "").strip().upper().replace(" ", "_")
    BAD_TAGS = {"IMPORTANT", "UPDATE", "VIRAL", "NEWS", "BREAKING", "TODAY", "CRIME", "GENERAL"}

    # If raw_category was SPORTS but text has zero sports terms, auto-correct!
    if raw_clean in ["SPORTS", "SPORTS_AWARDS"] and not has_sports:
        if has_odisha:
            return "ODISHA"
        elif has_science:
            return "SCIENCE_TECH"
        elif has_economy:
            return "ECONOMY"
        elif has_env:
            return "ENVIRONMENT"
        elif has_culture:
            return "CULTURE"
        elif has_intl:
            return "WORLD"
        elif has_gov:
            return "NATIONAL"
        return "NATIONAL"

    # Prioritize specialized domains
    if has_odisha:
        return "ODISHA"
    if has_sports:
        return "SPORTS"
    if has_science:
        return "SCIENCE_TECH"
    if has_economy:
        return "ECONOMY"
    if has_env:
        return "ENVIRONMENT"
    if has_culture:
        return "CULTURE"
    if has_intl:
        return "WORLD"
    if has_gov:
        return "NATIONAL"

    # Fallback to sanitized raw tag or NATIONAL
    if raw_clean and raw_clean not in BAD_TAGS:
        return raw_clean
    return "NATIONAL"

# ==============================================================================
# EXHAUSTIVE 3-TIER SOVEREIGN EXAM ENTITY MASTER REGISTRY (ODISHA • INDIA • WORLD)
# ==============================================================================
SOVEREIGN_EXAM_ENTITIES = {
    # 🏛️ Tier 1: Odisha State Governance, Boards, PSUs, Schemes, Geography & 30 Districts
    'opsc', 'ossc', 'osssc', 'bse odisha', 'chse', 'oavs', 'oshec', 'scert odisha',
    'odisha high court', 'sec odisha', 'oshrc', 'lokayukta odisha', 'osic',
    'omc', 'idco', 'gridco', 'optcl', 'ipicol', 'osacs', 'otdc', 'wodc', 'kbk',
    'osdma', 'src odisha', 'subhadra', 'mission shakti', 'bsky', 'kalia', 'lacmi', 'laccmi',
    'samrudha krushak', 'antyodaya', 'godabarisha mishra', 'madho singh', 'utkarsh odisha', 'balabhadra jaivik',
    'mo jungle jami', 'ama odisha', 'gopabandhu', 'madhu babu pension', 'similipal',
    'bhitarkanika', 'chilika', 'satkosia', 'gahirmatha', 'debrigarh', 'hirakud',
    'mahanadi', 'brahmani', 'baitarani', 'rushikulya', 'paradip port', 'dhamra port',
    'gopalpur port', 'odisha cabinet', 'odisha assembly', 'cm mohan majhi', 'governor of odisha',
    'utkal university', 'ravenshaw', 'vssut', 'ouat', 'biju patnaik university',
    
    # 🇮🇳 Tier 2: National Apex Institutions, Constitutional, Statutory, Banking & Defense (India)
    'supreme court', 'high court', 'election commission', 'eci', 'cag', 'finance commission',
    'upsc', 'nhrc', 'cic', 'cvc', 'law commission', 'rbi', 'sebi', 'nabard', 'sidbi',
    'exim bank', 'irdai', 'pfrda', 'gst council', 'cci', 'trai', 'fssai', 'ibbi',
    'isro', 'drdo', 'itr chandipur', 'barc', 'dae', 'csir', 'icmr', 'icar', 'imd', 'incois',
    'survey of india', 'gsi', 'ngt', 'cpcb', 'ntca', 'wildlife institute', 'wii',
    'botanical survey', 'bsi', 'zoological survey', 'zsi', 'niti aayog', 'ccea', 'ccs',
    'nhai', 'bis', 'fci', 'parliament of india', 'lok sabha', 'rajya sabha', 'president of india',
    'prime minister', 'union cabinet', 'pm-kusum', 'pm-kisan', 'pmay', 'ayushman bharat',
    'vande bharat', 'amrit bharat', 'kavach', 'dedicated freight corridor', 'sagarmala', 'bharatmala',
    
    # 🏆 Tier 3: Sports Championships, Grand Slams, Trophies & National Sports Honours
    'olympics', 'paralympics', 'asian games', 'commonwealth games', 'grand slam', 'wimbledon',
    'us open', 'french open', 'australian open', 'chess olympiad', 'fide', 'world chess championship',
    'thomas cup', 'uber cup', 'all england', 'durand cup', 'santosh trophy', 'ranji trophy',
    'khelo india', 'national games', 'dhyan chand', 'khel ratna', 'arjuna award', 'dronacharya award',
    'bcci', 'icc', 'fifa', 'hockey world cup', 'cricket world cup', 'badminton world federation', 'bwf',

    # 🎨 Tier 4: Arts, Culture, Literary Awards, Heritage & Global GK Honours
    'jnanpith', 'sahitya akademi', 'saraswati samman', 'vyas samman', 'booker prize',
    'nobel prize', 'ramon magsaysay', 'pulitzer', 'abel prize', 'fields medal', 'turing award',
    'padma vibhushan', 'padma bhushan', 'padma shri', 'bharat ratna', 'unesco world heritage',
    'intangible cultural heritage', 'dadasaheb phalke', 'national film awards', 'gi tag',
    
    # 🌿 Tier 5: Environment, Wildlife, Ecology & Climate Summits
    'ramsar site', 'tiger reserve', 'elephant reserve', 'national park', 'wildlife sanctuary',
    'biosphere reserve', 'iucn red list', 'project tiger', 'project elephant', 'project cheetah',
    'project lion', 'project dolphin', 'state of forest report', 'isfr', 'cop29', 'cop30', 'cop16',
    
    # 🌐 Tier 6: Global Multilateral, UN Specialized Agencies & International Bodies
    'unga', 'unsc', 'unesco', 'unep', 'undp', 'unicef', 'wto', 'fao', 'ilo',
    'wipo', 'wmo', 'imo', 'icao', 'iaea', 'unhcr', 'imf', 'world bank', 'ibrd', 'ida',
    'adb', 'aiib', 'ndb', 'wef', 'fatf', 'oecd', 'g20', 'g7', 'brics', 'sco', 'asean',
    'bimstec', 'saarc', 'iora', 'quad', 'i2u2', 'international solar alliance', 'isa', 'cdri',
    'iucn', 'ramsar', 'unfccc', 'icj', 'icc', 'interpol', 'wwf',
    'human development index', 'global innovation index', 'world happiness report', 'global hunger index'
}

SOVEREIGN_DYNAMIC_PATTERNS = [
    # 1. 🏛️ EXHAUSTIVE ODISHA GOVERNANCE, RECRUITMENT, ECOLOGY & SCHEME GRAMMAR
    r'\b(?:mo\s+(?:seba|ghara|school|college|bus|jungle|pokhari|bidyalaya|sarkar|parivar))\b',
    r'\b(?:ama\s+(?:bank|pokhari|odisha|hospital|sahara|ghara|krushi))\b',
    r'\b(?:mukhyamantri|mukhya\s+mantri)\s+[a-z\s]+(?:yojana|scheme|mission|kalyan|sahayata|puraskar)\b',
    r'\b(?:subhadra|mission\s+shakti|kalia|bsky|biju\s+swasthya|lacmi|laccmi|gopabandhu)\b',
    r'\b(?:utkal|kalinga|biju|madhu\s+babu)\s+[a-z\s]+(?:yojana|scheme|award|samman|puraskar)\b',
    r'\b(?:odisha\s+govt|government\s+of\s+odisha|odisha\s+cabinet|state\s+cabinet)\s+(?:clears|approves|sanctions|allocated|launches|unrolls|rolls\s+out|notifies|approves\s+₹)\b',
    r'\b(?:odisha\s+assembly|odisha\s+legislative\s+assembly)\s+(?:passes|enacts|amends)\b',
    r'\b(?:governor\s+of\s+odisha|chief\s+minister\s+of\s+odisha|cm\s+mohan\s+majhi)\b',
    r'\b(?:odisha\s+budget|supplementary\s+budget\s+for\s+odisha)\b',
    r'\b(?:odisha\s+[a-z\s]+\s+service\s+rules|odisha\s+civil\s+services|odisha\s+judicial\s+service)\b',
    r'\b(?:opsc|ossc|osssc|oavs|oshec|scert\s+odisha|bse\s+odisha|chse\s+odisha)\b',
    r'\b(?:odisha\s+police\s+recruitment|odisha\s+police\s+state\s+selection\s+board)\b',
    r'\b(?:bhubaneswar(?:\s*-\s*cuttack)?\s+metro\s+rail|metro\s+phase\s+[0-9]+)\b',
    r'\b(?:biju\s+expressway|capital\s+region\s+ring\s+road|coastal\s+highway\s+in\s+odisha)\b',
    r'\b(?:idco|omc|optcl|gridco|ipicol|otdc|osdma|src\s+odisha|wodc|kbk)\b',
    r'\b(?:paradip\s+port|dhamra\s+port|gopalpur\s+port|subarnarekha\s+port|astaranga\s+port)\b',
    r'\b(?:mega\s+lift\s+irrigation|barrage\s+on\s+(?:mahanadi|brahmani|baitarani|rushikulya|tel|subarnarekha))\b',
    r'\b(?:srimandir\s+parikrama|ratna\s+bhandar|ekamra\s+kshetra|samalei\s+project)\b',
    r'\b(?:jagannath\s+temple|lingaraj\s+temple|konark\s+sun\s+temple|tara\s+tarini|samaleswari)\b',
    r'\b(?:odisha\s+gi\s+tag|geographical\s+indication\s+for\s+odisha|gi\s+registry\s+odisha)\b',
    r'\b(?:olive\s+ridley|gahirmatha|rushikulya\s+rookery|devi\s+river\s+mouth)\b',
    r'\b(?:irrawaddy\s+dolphin|chilika\s+bird\s+census|similipal\s+tiger\s+census|bhitarkanika\s+crocodile)\b',
    # Universal Scheme Suffix & Budget Outlay Pattern
    r'\b[A-Za-z\s]+(?:\s+yojana|\s+scheme|\s+mission|\s+abhiyan|\s+prakalpa|\s+sahayata|\s+nidhi|\s+kosh|\s+policy\s+\d{4}|\s+guidelines|\s+portal)\b',
    r'\b(?:sanctioned|approved|allocated|outlay\s+of)\s+₹?\s*\d+(?:,\d+)*(?:\.\d+)?\s*(?:crore|lakh)\b',
    
    # 2. 🇮🇳 Indian National Policy, Schemes, Commissions & High Constitutional Appointments
    r'\b(?:pradhan\s+mantri|pm-|rashtriya|atmanirbhar|national\s+mission\s+on)\b',
    r'\b(?:ministry|department)\s+of\s+[a-z\s]+\b',
    r'\b(?:national|state)\s+(?:commission|authority|board|mission|tribunal|council)\b',
    r'\b(?:appointed\s+as\s+(?:the\s+)?(?:chief\s+justice|governor|chairman|director\s+general|chief\s+of\s+(?:army|naval|air)|cabinet\s+secretary|solicitor\s+general|attorney\s+general))\b',
    r'\b(?:yojana|scheme|portal|corridor|amendment|ordinance)\b',
    r'\b(?:cabinet\s+approved|sanctioned\s+₹|allocated\s+₹)\b',
    
    # 3. 💰 Banking, Monetary Metrics, Trade & National Infrastructure
    r'\b(?:monetary\s+policy\s+committee|repo\s+rate|reverse\s+repo|crr|slr|statutory\s+liquidity)\b',
    r'\b(?:gst\s+collection|gst\s+council\s+meeting|forex\s+reserves|trade\s+deficit|fdi\s+inflows?)\b',
    r'\b(?:retail\s+inflation|cpi\s+inflation|wpi\s+inflation|gdp\s+growth\s+rate|nso\s+estimates?)\b',
    r'\b(?:vande\s+bharat\s+train|bullet\s+train\s+corridor|kavach\s+anti-collision|dedicated\s+freight\s+corridor|expressway\s+inaugurated)\b',

    # 4. 🚀 Defense, Space, Deep Tech, Quantum & Science (India & World)
    r'\b(?:ins\s+[a-z]+|operation\s+[a-z]+|exercise\s+[a-z]+)\b',
    r'\b(?:pslv-[a-z0-9]+|gslv-[a-z0-9]+|sslv-[a-z0-9]+|gaganyaan|chandrayaan|aditya-l1|xposat|nisar)\b',
    r'\b(?:missile\s+test|ballistic\s+missile|cruise\s+missile|indigenously\s+developed|commissioned\s+into)\b',
    r'\b(?:spacecraft|telescope|lunar\s+mission|mars\s+rover|particle\s+physics|deep\s+sea\s+mission)\b',
    r'\b(?:quantum\s+computing|national\s+quantum\s+mission|semiconductor\s+fab|green\s+hydrogen\s+mission|supercomputer\s+param)\b',
    
    # 5. 🏆 Sports Milestones, Athletics, Trophies & Records
    r'\b(?:clinches?\s+gold|wins?\s+gold|silver\s+medal|bronze\s+medal|podium\s+finish|world\s+championship|grand\s+slam\s+title)\b',
    r'\b(?:chess\s+olympiad|grandmaster\s+title|fide\s+candidates|wimbledon\s+champion|olympic\s+quota|national\s+record)\b',
    r'\b(?:khelo\s+india\s+games|national\s+games\s+medal|thomas\s+cup|uber\s+cup|durand\s+cup|santosh\s+trophy)\b',

    # 6. 🎨 Culture, Heritage, Literary Awards & GI Tags (India & World)
    r'\b(?:gi\s+tag|geographical\s+indication|unesco\s+heritage|world\s+heritage\s+site|intangible\s+cultural\s+heritage)\b',
    r'\b(?:conferred\s+with|honoured\s+with|sahitya\s+akademi\s+award|jnanpith\s+award|saraswati\s+samman|booker\s+prize|nobel\s+prize|padma\s+award)\b',
    r'\b(?:archaeological\s+survey\s+of\s+india|asi\s+excavation|ancient\s+site\s+discovered)\b',

    # 7. 🌿 Ecology, Biodiversity, Wetlands & Wildlife Reserves
    r'\b(?:tiger\s+reserve|national\s+park|wildlife\s+sanctuary|ramsar\s+site|biosphere\s+reserve|elephant\s+reserve)\b',
    r'\b(?:critically\s+endangered|iucn\s+status|species\s+discovered|wildlife\s+census|tiger\s+census)\b',
    
    # 8. 🌐 International Treaties, Multilateral Summits, Blocs & Global Indices
    r'\b(?:treaty|accord|convention|protocol|declaration|pact|mou|bilateral\s+agreement)\s+(?:signed|ratified|adopted)\b',
    r'\b(?:summit|conference|cop\d+|g20|brics|asean|sco|quad|un\s+general\s+assembly)\s+(?:held|concluded|adopted|hosted)\b',
    r'\b(?:global\s+[a-z\s]+\s+index|world\s+[a-z\s]+\s+report|human\s+development\s+report)\s+(?:ranked|released|published)\b',
    r'\b(?:admitted\s+as\s+(?:the\s+)?\d+(?:st|nd|rd|th)?\s+member\s+of)\b'
]

# Pre-compiled word-boundary regexes to prevent substring collision (e.g. 'bee' in 'been', 'who' in 'whose')
SOVEREIGN_COMPILED_PATTERNS = [re.compile(r'\b' + re.escape(entity) + r'\b', re.IGNORECASE) for entity in SOVEREIGN_EXAM_ENTITIES]
SOVEREIGN_DYNAMIC_COMPILED = [re.compile(pat, re.IGNORECASE) for pat in SOVEREIGN_DYNAMIC_PATTERNS]

def is_sovereign_exam_entity(text: str) -> bool:
    """Returns True if the text contains an official Tier 1/2/3 institution or governance pattern."""
    t_lower = text.lower()
    if any(pat.search(t_lower) for pat in SOVEREIGN_COMPILED_PATTERNS):
        return True
    if any(pat.search(t_lower) for pat in SOVEREIGN_DYNAMIC_COMPILED):
        return True
    return False

def validate_slide_quality(slides, raw_text_payload):
    """
    Validates slide quality, accuracy & factual grounding:
    - Filters out generic headlines lacking specific named entities.
    - Applies deterministic 9-Category Expert AI Classifier.
    """
    import re
    import json
    GENERIC_PATTERNS = [
        r'government announces', r'new scheme launched', r'important update',
        r'senior officer appointed', r'new official appointed', r'major decision taken',
        r'key announcement', r'important notice released'
    ]

    valid_slides = []
    dropped_quality = []

    for slide in slides:
        if not isinstance(slide, dict):
            continue
        headline = slide.get("headline", "")
        h_lower = headline.lower()

        slide.pop("category", None)
        slide.pop("region", None)
        bullets = slide.get("bullets", [])

        # PLACEHOLDER CHECK: Drop any slide containing unreplaced brackets like [District Name], [River Name]
        if re.search(r'\[(district|river|block|taluk|ministry|state|agency|department|date|number|name|insert|amount|location)[^\]]*\]', json.dumps(slide).lower()):
            dropped_quality.append(f"'{headline[:55]}' (contains unreplaced template placeholder like [District Name])")
            print(f"⚫ QUALITY REJECT: '{headline[:55]}' contains unreplaced bracketed template placeholder.")
            continue

        slide_text_lower = json.dumps(slide).lower()
        has_sovereign_shield = is_sovereign_exam_entity(slide_text_lower)

        # 1. Generic headline check (Immune if sovereign entity is present)
        if not has_sovereign_shield and any(re.search(pat, h_lower) for pat in GENERIC_PATTERNS):
            dropped_quality.append(f"'{headline[:55]}' (Generic headline without specific entity)")
            print(f"🚫 QUALITY REJECT — Generic headline: '{headline[:55]}'")
            continue

        # Structured Evidence Verification Check (Sovereign Authority & Questionability)
        sovereign_entity = slide.get("sovereign_entity", "").strip()
        exam_fact = slide.get("exam_questionability_fact", "").strip()
        if sovereign_entity:
            if any(re.search(pat, sovereign_entity.lower()) for pat in HARD_POLITICAL_AND_NOISE_PATTERNS):
                dropped_quality.append(f"'{headline[:55]}' (Entity '{sovereign_entity}' matched non-exam blacklist)")
                print(f"🚫 ENTITY REJECT — '{sovereign_entity}' matched non-exam blacklist in: '{headline[:55]}'")
                continue

        # 2. Proper Noun / Named Entity Check (at least one capitalized proper noun or acronym)
        proper_nouns = re.findall(r'\b[A-Z][a-zA-Z0-9\-]+\b', headline)
        generic_starts = {'The', 'A', 'An', 'New', 'Daily', 'India', 'State', 'Union', 'Cabinet'}
        meaningful_nouns = [w for w in proper_nouns if w not in generic_starts or w in {'Odisha', 'OPSC', 'OSSC', 'OSSSC', 'DRDO', 'ISRO', 'RBI', 'GST'}]
        
        if not has_sovereign_shield and len(meaningful_nouns) == 0 and len(headline.split()) > 3:
            if not re.search(r'\d+', headline):
                dropped_quality.append(f"'{headline[:55]}' (Lacks specific named entity or entity details)")
                print(f"🚫 QUALITY REJECT — Lacks named entity: '{headline[:55]}'")
                continue

        # 3. Numeric & Date Claim Accuracy / Anti-Hallucination check
        nums_in_headline = re.findall(r'\b\d+(?:,\d+)*(?:\.\d+)?\b', headline)
        hallucinated = False
        for num in nums_in_headline:
            if len(num) >= 2:
                num_clean = num.replace(',', '')
                if num not in raw_text_payload and num_clean not in raw_text_payload.replace(',', ''):
                    hallucinated = True
                    break
        
        # 4. Strict Exam Date Verification (ensures AI never invents fake exam dates)
        combined_slide_text = f"{headline} " + " ".join(slide.get("bullets", []))
        raw_lower = raw_text_payload.lower()
        date_claims = re.findall(r'\b(?:\d{1,2}(?:\s*-\s*\d{1,2})?|\d{1,2}\s+to\s+\d{1,2})\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s*(?:\d{4})?\b', combined_slide_text, re.IGNORECASE)
        for date_claim in date_claims:
            d_clean = date_claim.lower().strip()
            m_match = re.search(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)', d_clean)
            if m_match:
                m_str = m_match.group(1)
                d_nums = re.findall(r'\b\d{1,2}\b', d_clean)
                if not (m_str in raw_lower and any(dn in raw_lower for dn in d_nums)):
                    hallucinated = True
                    dropped_quality.append(f"'{headline[:55]}' (Fact check failed: unverified date claim '{date_claim}' not in raw news)")
                    print(f"🚫 DATE FACT CHECK REJECT — Unverified date '{date_claim}' in: '{headline[:55]}'")
                    break

        if hallucinated:
            if not dropped_quality or not any(date_claim in dropped_quality[-1] for date_claim in date_claims):
                dropped_quality.append(f"'{headline[:55]}' (Fact check failed: contains unverified number or date not in raw news)")
                print(f"🚫 ACCURACY REJECT — Unverified figure in: '{headline[:55]}'")
            continue

        # 5. ZERO-RISK EXAM RELEVANCE FILTER (MANDATORY GATEKEEPER):
        # Uses global HARD_POLITICAL_AND_NOISE_PATTERNS defined at module level
        
        # ZERO-TRUST DEFAULT-DENY GATE:
        # Every published slide MUST contain a verified Sovereign Exam Entity or Syllabus Dynamic Pattern.
        # If it lacks a valid syllabus anchor, it is DROPPED by default.
        if not has_sovereign_shield:
            dropped_quality.append(f"'{headline[:55]}' (Zero-Trust Reject: Lacks verified sovereign institution, treaty, award, tournament, or statutory scheme anchor)")
            print(f"🚫 ZERO-TRUST SOVEREIGN REJECT — No syllabus anchor in: '{headline[:55]}'")
            continue

        if any(re.search(pat, slide_text_lower) for pat in HARD_POLITICAL_AND_NOISE_PATTERNS):
            dropped_quality.append(f"'{headline[:55]}' (Political rhetoric / commercial noise / verbal statement rejected)")
            print(f"🚫 EXAMINER BENCHMARK REJECT — Political rhetoric or noise skipped: '{headline[:55]}'")
            continue

        # QUANTITATIVE YIELD SCORE GATE (Calibrated Threshold >= 50/100: requires Sovereign Entity + at least one action/metric/MCQ fact)
        yield_score = 0
        breakdown = []
        if has_sovereign_shield:
            yield_score += 30
            breakdown.append("Sovereign Entity (+30)")
            
        if re.search(r'\b(?:clears|approves|sanctions|allocated|launches|unrolls|rolls\s+out|notifies|passes|enacts|amends|clinches|wins|conferred|appointed|commissioned|signed|ratified|adopted|ranked|released|rules|orders|upholds|strikes\s+down)\b', slide_text_lower):
            yield_score += 25
            breakdown.append("Statutory Action (+25)")
            
        if re.search(r'\b(?:\d+(?:,\d+)*(?:\.\d+)?\s*(?:crore|lakh|cr|%|percent|mw|km|tonnes?|usd|\$|₹|medal|rank|gold|silver|bronze))\b', slide_text_lower):
            yield_score += 25
            breakdown.append("Grounded Metric (+25)")
            
        if len(slide_text_lower.split()) >= 30 and (exam_fact or any(w in slide_text_lower for w in ["under", "by", "for", "dated", "aims to", "located in", "directed", "held that"])):
            yield_score += 20
            breakdown.append("MCQ Invertibility (+20)")
            
        if yield_score < 50:
            dropped_quality.append(f"'{headline[:55]}' (Quantitative Score Veto: {yield_score}/100 < 50 -> {', '.join(breakdown)})")
            print(f"🚫 QUANTITATIVE SCORE VETO — Score {yield_score}/100 for: '{headline[:55]}'")
            continue

        # Check for vague isolated directional fragments in headline (e.g. "in North", "in South", "in East", "in West")
        if re.search(r'\bin\s+(?:the\s+)?(?:north|south|east|west|central|coastal|northeast|northwest|southeast|southwest)(?:ern)?\b(?:\s*$|\s+(?:after|due|as|with|over))', headline.lower()):
            dropped_quality.append(f"'{headline[:55]}' (Vague directional fragment without specific Country/State/River)")
            print(f"🚫 GEOGRAPHIC REJECT — Vague directional location without country/state: '{headline[:55]}'")
            continue

        # 6. MANDATORY DYNAMIC BULLET VALIDATION & AUTO-RESCUE:
        bullets = slide.get("bullets", [])
        
        # AUTO-RESCUE: If Sovereign news has 2 dense bullets, auto-split to achieve 3 bullets rather than dropping
        if has_sovereign_shield and bullets and len(bullets) == 2:
            second_bullet = str(bullets[1])
            sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', second_bullet) if len(s.strip()) > 15]
            if len(sentences) >= 2:
                bullets = [bullets[0], sentences[0], " ".join(sentences[1:])]
                slide["bullets"] = bullets
                print(f"🔧 AUTO-RESCUE: Split dense sovereign bullet into 3 points for '{headline[:40]}'")

        if not bullets or len(bullets) < 3:
            dropped_quality.append(f"'{headline[:55]}' (Failed mandatory base 3-bullet requirement)")
            print(f"🚫 ZERO-FAIL RULE REJECT — Fewer than 3 bullets: '{headline[:55]}'")
            continue

        # Ensure all bullets (up to 5) are sanitized (no asterisks, no trailing ellipses)
        sanitized_bullets = []
        for b in bullets[:5]:
            sb = sanitize_zero_truncation(str(b).replace("**", "").replace("*", ""))
            if sb:
                sanitized_bullets.append(sb)
        slide["bullets"] = sanitized_bullets

        valid_slides.append(slide)

    if dropped_quality:
        print(f"⚠️ Quality/Accuracy Gate: dropped {len(dropped_quality)} invalid slide(s):")
        for dq in dropped_quality:
            print(f"   • {dq}")

    return valid_slides, dropped_quality


def format_current_affairs(raw_text_payload):
    print("[VERBOSE LOG] Formatting current affairs items via AI API...")

    if not DEEPSEEK_API_KEY:
        print("⚠️ DEEPSEEK_API_KEY is not set in environment or secrets. Skipping public broadcast.")
        return {"top_slides": [], "extra_highlights": [], "error": "NO_API_KEY"}

    if not raw_text_payload or len(raw_text_payload.strip()) == 0:
        print("⚠️ Raw news payload is empty. Nothing was scraped this run. Skipping public broadcast.")
        return {"top_slides": [], "error": "EMPTY_PAYLOAD"}

    today_date_str_prompt = datetime.now().strftime("%A, %d %B %Y")
    today_date_iso = datetime.now().strftime("%Y-%m-%d")
    from datetime import timedelta
    yesterday_date_iso = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    system_prompt = f"""
You are an Elite Senior Current Affairs Editor & Paper Setter for top-tier competitive examination prep platforms (UPSC CSE, OPSC OAS/OFS, Odisha Police SI, OSSC, SSC CGL, Banking, and Defence).
TODAY'S DATE IS: {today_date_str_prompt}.

CRITICAL INSTRUCTION:
1. Analyze the provided raw candidate news articles. Select ONLY genuine, factual, and exam-relevant current affairs news items published within the last 24-48 hours.
2. NEVER invent, hallucinate, or fabricate unverified facts or news.
3. Every slide MUST have strong competitive exam significance (Odisha State governance/schemes, National Polity, Constitutional amendments, Statutory rulings, Economy/RBI, Science/ISRO/DRDO, Defense exercises, Global Summits).
   - Select the highest-yield stories organically across Odisha, National, and International events.
   - Do NOT force artificial category batches. Prioritize genuine substantive merit and exam relevance.
4. OUTPUT RULE: You MUST return ONLY a pure valid JSON object matching the schema below. DO NOT output any introductory text, thought process, chain-of-thought, or markdown commentary outside the JSON object.

======================================================================
1. THE GOLDEN RULE OF EXAM INVERTIBILITY (THE MCQ TEST)
======================================================================
Before writing any slide, apply the "MCQ Invertibility Test":
"Can a real paper setter in UPSC/OPSC/OSSC formulate a factual 4-option Multiple Choice Question from this news with 1 unambiguous correct answer?"
• INVERTIBLE (ACCEPT):
  - "Which state cabinet approved ₹10,000 Cr outlay for the Subhadra Yojana?" ➔ YES (Odisha)
  - "Which Earth Observation Satellite was launched by ISRO using the SSLV launcher?" ➔ YES (EOS-08)
  - "Who won the Gold Medal in the Open Section at the 45th Chess Olympiad?" ➔ YES (Gukesh D / India)
  - "Which body conducts the Monetary Policy Committee meetings in India?" ➔ YES (RBI)
• NOT INVERTIBLE / ZERO EXAM VALUE (REJECT IMMEDIATELY):
  - Commercial film production disputes, celebrity tax cases (Dharma Productions, Karan Johar, etc.) ➔ REJECT
  - Philosophical op-eds, opinion essays, personal columns ➔ REJECT
  - Commercial consumer gadget launches (smartphones, watches) ➔ REJECT
  - Private corporate executive appointments (Colgate, Swiggy) ➔ REJECT
  - Routine municipal parking fees or minor road repairs ➔ REJECT
  - Ceremonial temple visits, floral tributes, condolences ➔ REJECT
  - Local petty crime, minor police arrests, accidents ➔ REJECT
  - Political rallies, mudslinging, party worker speeches ➔ REJECT

======================================================================
2. DYNAMIC & NATURAL BULLET POINT HEADINGS
======================================================================
Convert approved stories into 3 to 5 precise, highly educational bullet points.
- Create dynamic bold headings (2-4 words) that naturally match the story (e.g. "Subhadra Outlay Approved:", "Constitutional Mandate (Art 324):", "Mission Trajectory & Specs:").
- Write in clear, active, simple English.
- Complete Sentences: Every bullet point sentence must end with a period. Zero truncation or "...".

Output Requirements:
Return ONLY a valid JSON object matching this schema:
{{
  "top_slides": [
    {{
      "headline": "Short, powerful headline under 48 chars (Max 45 chars, ZERO '...')",
      "sovereign_entity": "Exact name of constitutional/statutory authority, state dept, or tournament (e.g. 'Odisha State Cabinet', 'ISRO', 'FIDE Chess Olympiad')",
      "exam_questionability_fact": "One unambiguous factual statement from which an examiner can formulate an exam MCQ (e.g. 'Odisha Cabinet sanctioned ₹10,000 Cr for Subhadra Yojana')",
      "bullets": [
        "Dynamic Heading 1 (2-4 words): Full detailed sentence (30-40 words) with concrete facts and zero truncation.",
        "Dynamic Heading 2 (2-4 words): Technical context, geographical/legal background (30-40 words) with zero truncation.",
        "Dynamic Heading 3 (2-4 words): Clear syllabus relevance, constitutional article, or strategic impact (30-40 words) with zero truncation."
      ]
    }}
  ],
  "extra_highlights": [
    "Specific news highlight 1 with exact names & figures",
    "Specific news highlight 2 with exact names & figures"
  ]
}}
"""

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    endpoint_url = f"{DEEPSEEK_BASE_URL.rstrip('/')}/chat/completions"
    model_name = "meta/llama-3.2-11b-vision-instruct" if "nvidia" in DEEPSEEK_BASE_URL else "deepseek-chat"

    # Pass the full balanced multi-stream payload
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": (
                f"Today is: {today_date_str_prompt}.\n\n"
                f"Analyze the following authentic scraped news candidates from official and trusted press feeds.\n"
                f"Extract the top genuine exam-relevant current affairs slides into JSON format:\n\n"
                f"{raw_text_payload[:8500]}"
            )}
        ],
        "temperature": 0.2,
        "max_tokens": 3500,
        "response_format": {"type": "json_object"}
    }

    global _ca_ai_model_used, _ca_ai_used_fallback
    _ca_ai_model_used = model_name
    _ca_ai_used_fallback = False

    def parse_ai_json_response(content_str: str):
        if not content_str or not content_str.strip():
            return None
        c_clean = content_str.strip()
        
        # Strip reasoning tags like <think>...</think> from newer models
        c_clean = re.sub(r'<think>[\s\S]*?<\/think>', '', c_clean, flags=re.IGNORECASE).strip()

        if "```json" in c_clean:
            c_clean = c_clean.split("```json")[1].split("```")[0].strip()
        elif "```" in c_clean:
            c_clean = c_clean.split("```")[1].split("```")[0].strip()

        # Extract strictly from first '{' to last '}'
        if "{" in c_clean:
            first_brace = c_clean.find("{")
            c_clean = c_clean[first_brace:]
            if "}" in c_clean:
                last_brace = c_clean.rfind("}")
                c_clean = c_clean[:last_brace+1]

        try:
            return json.loads(c_clean)
        except Exception:
            open_braces = c_clean.count("{") - c_clean.count("}")
            open_brackets = c_clean.count("[") - c_clean.count("]")
            repaired = c_clean.rstrip(", \n\t")
            if open_brackets > 0:
                repaired += "]" * open_brackets
            if open_braces > 0:
                repaired += "}" * open_braces
            try:
                return json.loads(repaired)
            except Exception:
                pass
        return None

    try:
        content = ""
        import time

        # Use active verified high-throughput NVIDIA NIM models with 75s timeout to allow full multi-slide JSON synthesis
        ai_tiers = [
            {
                "name": "NVIDIA Llama 3.2 11B Vision Instruct",
                "model": "meta/llama-3.2-11b-vision-instruct",
                "key": DEEPSEEK_API_KEY,
                "url": "https://integrate.api.nvidia.com/v1/chat/completions",
                "timeout": 75
            },
            {
                "name": "NVIDIA Llama 3.2 90B Vision Instruct",
                "model": "meta/llama-3.2-90b-vision-instruct",
                "key": DEEPSEEK_API_KEY,
                "url": "https://integrate.api.nvidia.com/v1/chat/completions",
                "timeout": 75
            },
            {
                "name": "NVIDIA Mistral Large",
                "model": "mistralai/mistral-large",
                "key": DEEPSEEK_API_KEY,
                "url": "https://integrate.api.nvidia.com/v1/chat/completions",
                "timeout": 75
            },
            {
                "name": "NVIDIA Nemotron Nano 3 30B",
                "model": "nvidia/nemotron-nano-3-30b-a3b",
                "key": os.getenv("NVIDIA_NEMOTRON_KEY") or DEEPSEEK_API_KEY,
                "url": "https://integrate.api.nvidia.com/v1/chat/completions",
                "timeout": 75
            }
        ]

        # Only add DeepSeek direct API if a native DeepSeek key (starting with sk-) is provided
        native_deepseek_key = (os.getenv("DEEPSEEK_API_KEY") or "").strip('"')
        if native_deepseek_key.startswith("sk-"):
            ai_tiers.append({
                "name": "DeepSeek Direct API",
                "model": "deepseek-chat",
                "key": native_deepseek_key,
                "url": "https://api.deepseek.com/v1/chat/completions",
                "timeout": 60
            })

        ai_success = False
        for tier_idx, tier in enumerate(ai_tiers):
            tier_name = tier["name"]
            model_name = tier["model"]
            key_val = str(tier["key"]).strip('"')
            call_url = tier["url"]
            timeout_val = tier["timeout"]

            call_headers = {"Authorization": f"Bearer {key_val}", "Content-Type": "application/json"}
            call_payload = {**payload, "model": model_name}

            for attempt in range(1, 3):
                try:
                    res = requests.post(call_url, headers=call_headers, json=call_payload, timeout=timeout_val)
                    if res.ok:
                        raw_c = res.json().get('choices', [{}])[0].get('message', {}).get('content', '')
                        if raw_c and raw_c.strip():
                            content = raw_c
                            _ca_ai_model_used = model_name
                            _ca_ai_used_fallback = (tier_idx > 0)
                            ai_success = True
                            print(f"✅ [{tier_name}] Responded successfully on attempt {attempt}.")
                            break
                    else:
                        print(f"⚠️ [{tier_name}] HTTP {res.status_code} on attempt {attempt}")
                except Exception as tier_err:
                    print(f"⚠️ [{tier_name}] Attempt {attempt} failed ({tier_err}). Retrying/Failing over...")
                time.sleep(1.5)

            if ai_success:
                break

        if not ai_success or not content:
            raise RuntimeError(f"All {len(ai_tiers)} AI Fallback Tiers exhausted without response.")

        ca_data = parse_ai_json_response(content)
        if not ca_data:
            raise ValueError(f"AI response could not be parsed into valid JSON. Raw content snippet: '{content[:100]}'")
        if isinstance(ca_data, dict) and "top_slides" in ca_data:
            print(f"✅ Successfully formatted Current Affairs items & extra highlights via AI.")
            
            seen_history = load_seen_news()
            seen_set = {normalize_title(t) for t in seen_history}
            new_published_titles = list(seen_history)

            unique_slides = []
            for slide in ca_data.get("top_slides", []):
                h_norm = normalize_title(slide.get("headline", ""))
                if h_norm not in seen_set:
                    seen_set.add(h_norm)
                    new_published_titles.append(slide.get("headline", ""))

                    new_bullets = []
                    for b in slide.get("bullets", []):
                        b_clean = sanitize_zero_truncation(b)
                        new_bullets.append(highlight_keypoint_label(b_clean))
                    slide["bullets"] = new_bullets
                    unique_slides.append(slide)

            # --- DATE & QUALITY & FACT-CHECK VERIFICATION GATES ---
            verified_slides, dropped_slides = verify_slide_dates(
                unique_slides, raw_text_payload, today_date_iso, yesterday_date_iso
            )
            quality_slides, dropped_quality = validate_slide_quality(verified_slides, raw_text_payload)

            ca_data["top_slides"] = quality_slides
            ca_data["_dropped_slides"] = dropped_slides
            ca_data["_dropped_quality"] = dropped_quality

            save_seen_news(new_published_titles)
            return ca_data

    except Exception as fmt_err:
        print(f"⚠️ AI API Formatting failed: {fmt_err}. Skipping fallback — no static fake news will be published.")
        return {"top_slides": [], "extra_highlights": [], "error": f"AI_FORMATTING_ERROR: {str(fmt_err)}"}

if __name__ == "__main__":
    from ca_scraper import scrape_current_affairs
    raw_items, raw_payload = scrape_current_affairs()
    items = format_current_affairs(raw_payload)
    print(json.dumps(items, indent=2))
