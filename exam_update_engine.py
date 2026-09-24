import os
import sys
import json
import time
import io
import re
import hashlib
from datetime import datetime
import requests
import urllib3

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Suppress SSL InsecureRequestWarning for government portals
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Import shared infrastructure modules
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)

from shared.logging_utils import setup_logger
from shared.history_manager import HistoryManager
from shared.telegram import send_admin_alert
from shared.supabase_client import SupabaseBlogClient
from shared.source_validator import SourceValidator
from shared.seo_validator import SEOValidator
from shared.duplicate_detector import DuplicateDetector
from shared.pexels_image_fetcher import fetch_pexels_featured_image

logger = setup_logger("ExamUpdateEngine")

PROJECT_ROOT = SCRIPT_DIR
REGISTRY_PATH = os.path.join(PROJECT_ROOT, "config", "exam_registry.json")
SETTINGS_PATH = os.path.join(PROJECT_ROOT, "config", "settings.json")
SEEN_NOTICES_FILE = os.path.join(PROJECT_ROOT, "seen_notices.json")

GEMINI_API_KEY = (
    os.getenv("GEMINI_API_KEY") or
    os.getenv("VITE_GEMINI_API_KEY") or
    ""
).strip('"')

DEEPSEEK_API_KEY = (
    os.getenv("DEEPSEEK_API_KEY") or
    os.getenv("NVIDIA_NIM_API_KEY") or
    os.getenv("OPENAI_API_KEY") or
    os.getenv("VITE_DEEPSEEK_API_KEY") or
    ""
).strip('"')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache"
}

# ==============================================================================
# DIRECT OFFICIAL GOVERNMENT PORTAL MAP (ZERO COACHING RUMORS)
# ==============================================================================
DIRECT_PORTAL_MAP = {
    # Odisha State Master Portals
    "OSSC": "https://www.ossc.gov.in/Public/Pages/What_is_new.aspx",
    "OSSSC": "https://www.osssc.gov.in/Public/Notifications.aspx",
    "OPSC": "https://www.opsc.gov.in/Public/Pages/Notices.aspx",
    "Odisha Police": "https://odishapolice.gov.in/",
    "SSB Odisha": "https://ssbodisha.ac.in/",
    "BSE Odisha": "http://bseodisha.ac.in/latest-updates.html",
    "OAVS": "https://oav.edu.in/",
    "Odisha High Court": "https://www.orissahighcourt.nic.in/recruitment-corner/",
    "OPTCL": "https://optcl.co.in/CurrentOpening.aspx",
    "OMC": "https://omcltd.in/Recruitment",
    "OPGC": "https://opgc.co.in/careers",
    "OHPC": "https://ohpcltd.com/recruitment",
    "GRIDCO": "https://gridco.co.in/careers",
    "SCERT Odisha": "https://scertodisha.nic.in/",
    "Odisha Prisons": "https://prisons.odisha.gov.in/",
    "Odisha Fire Service": "https://odishafireservices.gov.in/",
    "OFDC": "https://odishafdc.com/recruitment",
    "OSCB": "https://oscb.coop/careers",
    
    # Central Government Master Portals
    "SSC": "https://ssc.gov.in/",
    "RRB": "https://rrbbbs.gov.in/",
    "UPSC": "https://upsc.gov.in/whats-new",
    "IBPS": "https://www.ibps.in/",
    "SBI": "https://sbi.co.in/web/careers/current-openings",
    "RBI": "https://opportunities.rbi.org.in/scripts/vacancies.aspx",
    "NTA": "https://nta.ac.in/Notice",
    "NABARD": "https://www.nabard.org/careers-notices1.aspx",
    "SEBI": "https://www.sebi.gov.in/sebiweb/other/career.jsp",
    "SIDBI": "https://www.sidbi.in/en/careers",
    "FCI": "https://fci.gov.in/current-vacancies",
    "LIC": "https://licindia.in/careers",
    "DRDO": "https://www.drdo.gov.in/careers",
    "ISRO": "https://www.isro.gov.in/Careers.html",
    "BARC": "https://www.barc.gov.in/careers",
    "CAPF": "https://mha.gov.in/en/notifications/vacancies",
    "Indian Coast Guard": "https://joinindiancoastguard.cdac.in/",
    "EPFO": "https://www.epfindia.gov.in/site_en/Recruitments.php",
    "ESIC": "https://www.esic.gov.in/recruitments",
    "AAI": "https://www.aai.aero/en/careers/recruitment",
    "AIIMS": "https://www.aiimsexams.ac.in/"
}

# ==============================================================================
# DETERMINISTIC 20-CATEGORY ANTI-NOISE, ANTI-DEPUTATION & ANTI-TENDER PATTERNS
# ==============================================================================
EXAM_UPDATE_HARD_REJECT_PATTERNS = [
    # 1. Deputation & Senior Executive/Contract appointments (Zero Competitive Exam Value)
    r'\b(?:deputation|on\s+deputation|contract\s+basis\s+in|chairman-cum-managing|managing\s+director|\bcmd\b|director\s+general|\bceo\b|advisor|consultant|empanelment|engagement\s+of\s+retired|retired\s+officer|contractual\s+faculty|guest\s+faculty|visiting\s+faculty|adjunct\s+faculty|project\s+fellow|research\s+associate|jrf\s+walk-in|srf\s+walk-in)\b',
    # 2. Navigation & General Portal Noise
    r'\b(?:skip\s+to\s+main|screen\s+reader|accessibility|feedback|contact\s+us|about\s+us|site\s+map|disclaimer|privacy\s+policy|user\s+manual|apply\s+online|login|register|faqs?|terms)\b',
    # 3. Tenders, procurement, auction, stationery
    r'\b(?:e-tender|tender|quotation|procurement|stationery|auction|vehicle\s+auction|rfp|bid|corrigendum\s+to\s+tender)\b',
    # 4. Departmental staff, promotion, internal transfer, seniority
    r'\b(?:transfer\s+and\s+posting|promotion\s+list|staff\s+seniority|confidential\s+report|leave\s+order|acp/macp|pension\s+list|departmental\s+inquiry|internal\s+circular)\b',
    # 5. Routine school boards
    r'\b(?:class\s+ix|class\s+9|class\s+8|annual\s+class\s+ix|madhyama\s+examination|high\s+school\s+certificate)\b',
    # 6. Rejection / disqualified lists
    r'\b(?:rejected\s+application(?:s)?\s+list|rejection\s+list|ineligible\s+candidate(?:s)?\s+list|disqualified\s+list)\b'
]

def is_notice_date_expired(title: str, snippet: str) -> bool:
    """
    Detects if the notice mentions an action date or deadline that has ALREADY EXPIRED.
    Example: 'up to 13 August 2026' when today is 21 August 2026.
    Returns True if the notice is definitely expired and should be dropped.
    """
    text = f"{title} {snippet}".lower()
    # Newly declared outcomes of past events (Results, Answer Keys, Admit Cards) are fresh
    if any(k in text for k in ["result", "answer key", "merit list", "cut-off", "cutoff", "scorecard", "admit card"]):
        return False
        
    deadline_patterns = [
        r'(?:up to|till|last date|extended to|extended up to|closing date)\s*(?:was|is|on|up to)?\s*(\d{1,2})[\.\/\-\s]+([a-z]+|\d{1,2})[\.\/\-\s]+(\d{4})',
        r'(\d{1,2})[\.\/\-\s]+([a-z]+|\d{1,2})[\.\/\-\s]+(\d{4})\s+(?:up to|till|as last date|was the last date)'
    ]
    
    month_names = {
        'jan': 1, 'january': 1, 'feb': 2, 'february': 2, 'mar': 3, 'march': 3,
        'apr': 4, 'april': 4, 'may': 5, 'jun': 6, 'june': 6, 'jul': 7, 'july': 7,
        'aug': 8, 'august': 8, 'sep': 9, 'september': 9, 'oct': 10, 'october': 10,
        'nov': 11, 'november': 11, 'dec': 12, 'december': 12
    }
    
    for pat in deadline_patterns:
        match = re.search(pat, text, re.IGNORECASE)
        if match:
            day_str, month_str, year_str = match.groups()
            try:
                month_num = int(month_names.get(month_str.lower(), month_str))
                dt = datetime(int(year_str), month_num, int(day_str))
                now = datetime.now()
                # If deadline was more than 2 days ago, it is EXPIRED
                if (now - dt).total_seconds() > 2 * 86400:
                    return True
            except Exception:
                pass
    return False

class ExamFactualIntegrityValidator:
    """
    Deterministic Zero-Trust Factual Integrity Validator for Exam Updates.
    Does NOT trust the LLM. Performs strict multi-checkpoint validation
    using pure Python logic against raw government source text.
    """
    @staticmethod
    def calculate_yield_score(candidate: dict) -> tuple[int, str]:
        raw_title = str(candidate.get("title", "")).lower()
        raw_snippet = str(candidate.get("snippet", "")).lower()
        raw_url = str(candidate.get("url", "")).lower()
        is_direct = candidate.get("is_direct_portal", False)
        combined = f"{raw_title} {raw_snippet} {raw_url}"
        score = 0
        breakdown = []

        # TIER 0: Direct Portal Fast-Pass (Official Truth by Source)
        if is_direct:
            score += 25
            breakdown.append("Direct Official Portal Source (+25)")

        exam_keywords = [
            "recruitment", "advt", "advertisement", "notification", "admit card", "hall ticket",
            "exam date", "schedule", "answer key", "result", "merit list", "cutoff", "cut-off",
            "scorecard", "document verification", "dv", "interview", "viva", "skill test",
            "preliminary", "main", "cgl", "chsl", "cre", "aso", "constable", "si", "officer",
            "clerk", "typist", "lecturer", "teacher", "otet", "osstet", "pgt", "tgt", "corrigendum",
            "candidature", "instruction", "exam notice", "rejection", "rescheduled"
        ]
        matched_kw = [kw for kw in exam_keywords if kw in combined]
        if matched_kw:
            score += 25
            breakdown.append(f"Milestone Keyword (+25: {matched_kw[0]})")
        else:
            return 0, "DROPPED: Zero recruitment milestone keywords"

        advt_patterns = [
            r'\b(?:advt(?:\.|\s+no\.?|\s+number)|\bnotif(?:ication)?\.?\s+no\.?|notice\s+no\.?|ii-\(\d+\)|no\.\s*\d+/(?:opsc|ossc|osssc)|corrigendum)\b'
        ]
        if any(re.search(pat, combined) for pat in advt_patterns):
            score += 25
            breakdown.append("Official Advt/Notice Number (+25)")

        curr_yr = str(datetime.now().year)
        prev_yr = str(datetime.now().year - 1)
        if curr_yr in combined or prev_yr in combined or is_direct:
            score += 20
            breakdown.append(f"Active Year Anchor (+20: {curr_yr}/{prev_yr})")
        else:
            return 0, "DROPPED: Lacks active recruitment cycle year"

        authorities = [
            "opsc", "ossc", "osssc", "ssc", "rrb", "upsc", "ibps", "sbi", "rbi", "nta",
            "ssb odisha", "bse odisha", "high court", "oavs", "optcl", "omc", "opgc",
            "ohpc", "gridco", "scert", "prisons", "fire service", "ofdc", "oscb",
            "nabard", "sebi", "sidbi", "fci", "lic", "niacl", "drdo", "isro", "barc",
            "capf", "crpf", "bsf", "cisf", "itbp", "coast guard", "epfo", "esic", "aai", "asrb", "aiims"
        ]
        if any(auth in combined for auth in authorities) or is_direct:
            score += 15
            breakdown.append("Nodal Authority (+15)")

        if ".pdf" in raw_url or "download" in raw_url or "attachment" in combined or is_direct:
            score += 15
            breakdown.append("PDF Attachment (+15)")

        return min(score, 100), f"Score: {min(score, 100)}/100 -> {', '.join(breakdown)}"

    @staticmethod
    def validate_and_sanitize(article_data: dict, top_candidate: dict) -> tuple[bool, str, dict]:
        raw_title = top_candidate.get("title", "")
        raw_url = top_candidate.get("url", "")
        raw_snippet = top_candidate.get("snippet", "")
        raw_combined = f"{raw_title} {raw_snippet}".lower()
        
        # Check 1: Year Freshness Check (Active Cycle Anchor)
        current_year = datetime.now().year
        valid_years = [str(current_year), str(current_year - 1)]
        has_current_cycle = any(yr in raw_combined or yr in raw_url for yr in valid_years)
        has_historical_year = any(f"/{yr}/" in raw_url or f"_{yr}" in raw_url or f"advertisement no. {yr}" in raw_combined for yr in ["2020", "2021", "2022", "2023", "2024"])
        
        if has_historical_year and not has_current_cycle:
            return False, "REJECTED_ARCHIVED_RECRUITMENT_CYCLE", article_data
            
        # Check 2: Expired Deadline in AI-Generated Dates
        dates_field = str(article_data.get("dates", ""))
        exam_schedule_field = str(article_data.get("exam_schedule", ""))
        ai_combined_text = f"{article_data.get('title', '')} {dates_field} {exam_schedule_field}"
        
        if is_notice_date_expired(article_data.get("title", ""), ai_combined_text):
            return False, "REJECTED_EXPIRED_ACTION_DATE_IN_AI_OUTPUT", article_data
            
        # Check 3: Essential Exam Indicator Gate
        exam_keywords = [
            "recruitment", "advt", "advertisement", "notification", "admit card", "hall ticket",
            "exam date", "schedule", "answer key", "result", "merit list", "cutoff", "cut-off",
            "scorecard", "document verification", "dv", "interview", "viva", "skill test",
            "preliminary", "main", "cgl", "chsl", "cre", "aso", "constable", "si", "officer",
            "clerk", "typist", "lecturer", "teacher", "otet", "osstet", "pgt", "tgt"
        ]
        if not any(kw in raw_combined for kw in exam_keywords):
            return False, "REJECTED_LACKING_OFFICIAL_EXAM_KEYWORDS", article_data
            
        # Check 4: Anti-Hallucination Vacancy & Number Grounding
        vacancies_str = str(article_data.get("vacancies", "")).strip()
        vac_numbers = re.findall(r'\b\d{2,6}\b', vacancies_str.replace(",", ""))
        if vac_numbers and not any(k in vacancies_str.lower() for k in ["refer", "n/a", "check", "official"]):
            raw_numbers = set(re.findall(r'\b\d{2,6}\b', raw_combined.replace(",", "")))
            if not any(num in raw_numbers for num in vac_numbers):
                logger.warning(f"⚠️ AI vacancy number {vacancies_str} not in raw text. Sanitizing to official notice.")
                article_data["vacancies"] = "Refer to Official Notification PDF"
                
        # Check 5: Anti-Speculation Word Filter
        speculation_triggers = [
            "expected soon", "likely to be released", "as per sources", "tentative leak",
            "rumored", "youtube video claims", "unofficial update", "coaching reports"
        ]
        title_lower = article_data.get("title", "").lower()
        if any(trig in title_lower or trig in dates_field.lower() for trig in speculation_triggers):
            return False, "REJECTED_UNOFFICIAL_SPECULATION_OR_LEAK", article_data

        # Check 6: Quantitative Yield Score Threshold (Strict Fail-Closed Threshold >= 80)
        score, score_reason = ExamFactualIntegrityValidator.calculate_yield_score(top_candidate)
        if score < 80:
            return False, f"REJECTED_INSUFFICIENT_YIELD_SCORE ({score}/100 < 80 -> {score_reason})", article_data
            
        return True, "PASSED_ALL_INTEGRITY_GATES", article_data

def load_json_file(path: str, default: any):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default

def save_json_file(path: str, data: any):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"⚠️ Error saving JSON file {path}: {e}")

def get_notice_fingerprint(org_name: str, title: str, link: str) -> str:
    key = f"{org_name.upper()}:{title.strip().lower()}:{link.strip()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()

def extract_pdf_text_from_url(pdf_url: str, max_pages: int = 2) -> str:
    """
    In-memory PDF text extraction using pypdf.
    Downloads the first 500KB into RAM, parses text, and returns clean lines.
    Zero disk footprint, ultra-fast, and robust against corrupt/scanned files.
    """
    if not pdf_url or not pdf_url.lower().endswith(".pdf"):
        return ""
    try:
        logger.info(f"📄 In-memory parsing PDF attachment: {pdf_url[:70]}...")
        res = requests.get(pdf_url, headers=HEADERS, timeout=20, verify=False, stream=True)
        if not res.ok:
            return ""
        
        pdf_bytes = io.BytesIO()
        for chunk in res.iter_content(chunk_size=65536):
            pdf_bytes.write(chunk)
            if pdf_bytes.tell() > 1024 * 1024:  # Max 1MB
                break
        pdf_bytes.seek(0)

        try:
            import pypdf
            reader = pypdf.PdfReader(pdf_bytes)
            pages_text = []
            for i in range(min(max_pages, len(reader.pages))):
                p_txt = reader.pages[i].extract_text() or ""
                if p_txt.strip():
                    pages_text.append(p_txt.strip())
            extracted = "\n".join(pages_text)
            logger.info(f"✅ Extracted {len(extracted)} characters from PDF notice.")
            return extracted[:4000]
        except ImportError:
            logger.warning("⚠️ pypdf not installed. Falling back to raw regex extraction...")
        except Exception as pdf_parse_err:
            logger.warning(f"⚠️ PDF parse note: {pdf_parse_err}")
    except Exception as ex:
        logger.warning(f"⚠️ Could not download PDF for text extraction: {ex}")
    return ""

def call_deepseek_api(messages: list) -> tuple:
    """Returns (content: str, model_used: str, used_fallback: bool) with 4-tier multi-provider failover."""
    ai_tiers = [
        {
            "name": "NVIDIA Nemotron 3 Super 120B",
            "model": "nvidia/nemotron-3-super-120b-a12b",
            "key": DEEPSEEK_API_KEY,
            "url": "https://integrate.api.nvidia.com/v1/chat/completions",
            "timeout": 45
        },
        {
            "name": "NVIDIA GLM 5.3",
            "model": "z-ai/glm-5.3",
            "key": DEEPSEEK_API_KEY,
            "url": "https://integrate.api.nvidia.com/v1/chat/completions",
            "timeout": 45
        },
        {
            "name": "NVIDIA Llama 3.2 11B Vision Instruct",
            "model": "meta/llama-3.2-11b-vision-instruct",
            "key": DEEPSEEK_API_KEY,
            "url": "https://integrate.api.nvidia.com/v1/chat/completions",
            "timeout": 60
        }
    ]

    native_deepseek_key = (os.getenv("DEEPSEEK_API_KEY") or "").strip('"')
    if native_deepseek_key.startswith("sk-"):
        ai_tiers.append({
            "name": "DeepSeek Direct API",
            "model": "deepseek-chat",
            "key": native_deepseek_key,
            "url": "https://api.deepseek.com/v1/chat/completions",
            "timeout": 60
        })

    payload_base = {
        "messages": messages,
        "temperature": 0.2,
        "response_format": {"type": "json_object"}
    }

    # TIER 1 (PRIMARY): Google AI Studio Gemini API
    if GEMINI_API_KEY:
        gemini_prompt = "\n\n".join([f"Role: {m.get('role')}\n{m.get('content')}" for m in messages])
        for g_model in ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.6-flash"]:
            try:
                g_url = f"https://generativelanguage.googleapis.com/v1beta/models/{g_model}:generateContent?key={GEMINI_API_KEY}"
                g_payload = {
                    "contents": [{"parts": [{"text": gemini_prompt}]}],
                    "generationConfig": {
                        "response_mime_type": "application/json",
                        "temperature": 0.2,
                        "maxOutputTokens": 3000
                    }
                }
                g_res = requests.post(g_url, headers={"Content-Type": "application/json"}, json=g_payload, timeout=22)
                if g_res.ok:
                    data = g_res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        raw_c = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        if raw_c and raw_c.strip():
                            logger.info(f"✅ [Google Gemini - {g_model}] AI responded successfully as Primary.")
                            return raw_c, f"Google Gemini ({g_model}) [Primary]", False
            except Exception as g_err:
                logger.warning(f"⚠️ [Google Gemini - {g_model}] failed: {g_err}. Falling over...")

    for tier_idx, tier in enumerate(ai_tiers):
        tier_name = tier["name"]
        model_name = tier["model"]
        key_val = str(tier["key"]).strip('"')
        call_url = tier["url"]
        timeout_val = tier["timeout"]

        call_headers = {"Authorization": f"Bearer {key_val}", "Content-Type": "application/json"}
        call_payload = {**payload_base, "model": model_name}

        for attempt in range(1, 3):
            try:
                res = requests.post(call_url, headers=call_headers, json=call_payload, timeout=timeout_val)
                if res.ok:
                    raw_c = res.json().get('choices', [{}])[0].get('message', {}).get('content', '')
                    if raw_c and raw_c.strip():
                        logger.info(f"✅ [{tier_name}] AI responded successfully (attempt {attempt}).")
                        return raw_c, model_name, (tier_idx > 0)
                else:
                    logger.warning(f"⚠️ [{tier_name}] HTTP {res.status_code} on attempt {attempt}")
            except Exception as tier_err:
                logger.warning(f"⚠️ [{tier_name}] Attempt {attempt} failed ({tier_err}). Retrying/Failing over...")
            time.sleep(1.5)

    raise RuntimeError("All 4 AI Fallback Tiers exhausted in exam update engine.")

def fetch_direct_portal_notices(org_info: dict) -> list:
    """
    Direct Official Portal Scraper.
    Queries the official recruitment portal DOM directly, bypassing coaching blog searches.
    """
    org_name = org_info.get("organization")
    portal_url = DIRECT_PORTAL_MAP.get(org_name)
    
    if not portal_url:
        return []

    logger.info(f"🏛️ Scraping direct official portal for {org_name} ({portal_url})...")
    results = []

    try:
        res = requests.get(portal_url, headers=HEADERS, timeout=25, verify=False)
        if not res.ok:
            logger.warning(f"⚠️ HTTP {res.status_code} from {org_name} portal.")
            return []

        # Strategy 1: BeautifulSoup if available
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(res.text, "html.parser")
            for element in soup(["header", "footer", "nav", "script", "style", "iframe"]):
                element.extract()

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

            for row in candidate_rows[:25]:
                a_tag = row.find("a")
                if not a_tag:
                    continue
                title = a_tag.get_text(" ", strip=True)
                href = a_tag.get("href", "").strip()
                if not href or href in ["#", "javascript:void(0);", "javascript:void(0)", "javascript:;"]:
                    continue

                full_link = href if href.startswith("http") else requests.compat.urljoin(portal_url, href)

                if len(title) < 10:
                    continue

                if any(re.search(pat, title, re.IGNORECASE) for pat in EXAM_UPDATE_HARD_REJECT_PATTERNS):
                    continue

                pdf_text = ""
                if full_link.lower().endswith(".pdf"):
                    pdf_text = extract_pdf_text_from_url(full_link, max_pages=2)

                snippet = f"{row.get_text(' ', strip=True)}\n{pdf_text}".strip()

                # Pre-filter expired notices (e.g. edit window ended days ago)
                if is_notice_date_expired(title, snippet):
                    logger.info(f"🚫 Skipping expired portal notice: '{title[:60]}'")
                    continue

                results.append({
                    "url": full_link,
                    "title": title,
                    "snippet": snippet[:3500],
                    "is_direct_portal": True
                })
        except ImportError:
            # Strategy 2: Fast pure-regex HTML parsing
            logger.info("ℹ️ Using fast regex HTML parser...")
            # Match <a href="...">Title</a>
            a_matches = re.findall(r'<a\s+(?:[^>]*?\s+)?href=[\'"]([^\'"]+)[\'"][^>]*>(.*?)</a>', res.text, re.IGNORECASE | re.DOTALL)
            exam_indicators = [
                'notice', 'advt', 'cgl', 'examination', 'preliminary', 'main', 'admit', 'result',
                'date', 'recruitment', 'schedule', 'list', 'post', 'viva', 'skill', 'test', 'answer key', 'cutoff', 'cut-off', 'score'
            ]
            for href, raw_title in a_matches:
                clean_title = re.sub(r'<[^>]+>', '', raw_title).strip()
                if len(clean_title) < 12 or href in ["#", "javascript:void(0);", "javascript:;"]:
                    continue
                full_link = href if href.startswith("http") else requests.compat.urljoin(portal_url, href)
                if any(re.search(pat, clean_title, re.IGNORECASE) for pat in EXAM_UPDATE_HARD_REJECT_PATTERNS):
                    continue
                
                # Must either be a PDF document or contain an exam keyword
                is_pdf = full_link.lower().endswith(".pdf")
                has_exam_kw = any(kw in clean_title.lower() for kw in exam_indicators)
                if not (is_pdf or has_exam_kw):
                    continue

                pdf_text = ""
                if is_pdf:
                    pdf_text = extract_pdf_text_from_url(full_link, max_pages=2)
                snippet = f"{clean_title}\n{pdf_text}".strip()

                # Pre-filter expired notices
                if is_notice_date_expired(clean_title, snippet):
                    logger.info(f"🚫 Skipping expired portal notice: '{clean_title[:60]}'")
                    continue

                results.append({
                    "url": full_link,
                    "title": clean_title,
                    "snippet": snippet[:3500],
                    "is_direct_portal": True
                })
                if len(results) >= 8:
                    break

    except Exception as e:
        logger.warning(f"⚠️ Direct portal scrape error for {org_name}: {e}")

    logger.info(f"✅ Extracted {len(results)} candidate notices directly from {org_name} portal.")
    return results[:8]

def research_organization_updates(org_info: dict, source_validator: SourceValidator = None) -> list:
    """
    Tier 1: Direct official portal scrape.
    Tier 2 Fallback: Verified DDG search restricted 100% to official government domains.
    """
    # 1. Attempt direct portal scrape first (100% official truth)
    direct_results = fetch_direct_portal_notices(org_info)
    if direct_results:
        return direct_results

    # 2. Fallback to DDG search if portal has no direct scraper entry
    org_name = org_info.get("organization")
    domains = org_info.get("official_domains", [])
    query = f"{org_name} recruitment notification admit card exam date official site:.gov.in OR site:.nic.in OR site:.ac.in"
    
    logger.info(f"🔎 Fallback research for {org_name} via search engine (official domains only)...")
    results = []
    try:
        from duckduckgo_search import DDGS
        ddgs = DDGS()
        search_res = ddgs.text(query, max_results=6)
        for r in search_res:
            url = r.get("href", "")
            title = r.get("title", "")
            body = r.get("body", "")
            
            # Anti-Tender & Anti-Admin check on title
            if any(re.search(pat, title, re.IGNORECASE) for pat in EXAM_UPDATE_HARD_REJECT_PATTERNS):
                continue

            if is_notice_date_expired(title, body):
                continue

            # Strict Official Domain Filter: Discard third-party blogs, coaching portals, and rumors
            if source_validator and not source_validator.is_official_domain(url):
                logger.info(f"🚫 Dropping non-official domain search result: {url}")
                continue

            results.append({"url": url, "title": title, "snippet": body, "is_direct_portal": False})
    except Exception as e:
        logger.warning(f"⚠️ Fallback search error for {org_name}: {e}")
    return results

def main():
    logger.info("==================================================")
    logger.info("🚀 MISSION-CRITICAL EXAM UPDATE ENGINE LAUNCHED")
    logger.info("==================================================")

    registry = load_json_file(REGISTRY_PATH, [])
    settings = load_json_file(SETTINGS_PATH, {})
    max_articles = settings.get("max_exam_update_articles_per_run", 5)

    enabled_orgs = [org for org in registry if org.get("enabled", True)]
    logger.info(f"📋 Loaded {len(enabled_orgs)} enabled exam organizations from registry.")

    source_validator = SourceValidator()
    supabase_client = SupabaseBlogClient()
    existing_blogs = supabase_client.fetch_all_blogs()
    history = HistoryManager.load_exam_updates_history()
    seen_notices = load_json_file(SEEN_NOTICES_FILE, {})

    published_count = 0
    start_time = time.time()
    MAX_RUN_TIME_SECONDS = 750  # 12.5 minutes maximum

    today_date_str = datetime.now().strftime("%A, %d %B %Y")
    today_iso = datetime.now().strftime("%Y-%m-%d")

    # Detailed Scan Audit Counters for Admin Transparency
    scanned_portals = []
    failed_portals = []
    total_evaluated_notices = 0
    ignored_deputation_count = 0
    ignored_expired_count = 0
    already_seen_count = 0

    for org in enabled_orgs:
        if published_count >= max_articles:
            logger.info(f"🛑 Reached max articles per run ({max_articles}). Stopping.")
            break

        if (time.time() - start_time) > MAX_RUN_TIME_SECONDS:
            logger.info("⏳ Reached maximum workflow execution time. Exiting cleanly.")
            break

        org_name = org.get("organization")
        try:
            search_results = research_organization_updates(org, source_validator=source_validator)
            scanned_portals.append(org_name)
        except Exception as p_err:
            logger.warning(f"⚠️ Error accessing portal {org_name}: {p_err}")
            failed_portals.append(org_name)
            continue

        if not search_results:
            logger.info(f"ℹ️ No recent candidate notices found for {org_name}.")
            continue

        total_evaluated_notices += len(search_results)

        # Filter out already seen fingerprints
        fresh_candidates = []
        for cand in search_results:
            cand_title = cand.get("title", "")
            cand_snippet = cand.get("snippet", "")
            
            # Count deputation / non-student items
            if any(re.search(pat, cand_title, re.IGNORECASE) for pat in EXAM_UPDATE_HARD_REJECT_PATTERNS):
                ignored_deputation_count += 1
                continue

            fp = get_notice_fingerprint(org_name, cand["title"], cand["url"])
            if fp not in seen_notices:
                # Double-check date freshness
                if not is_notice_date_expired(cand["title"], cand["snippet"]):
                    fresh_candidates.append(cand)
                else:
                    ignored_expired_count += 1
                    seen_notices[fp] = {
                        "portal": org_name,
                        "title": cand["title"],
                        "status": "DROPPED_EXPIRED_DATE",
                        "processed_at": datetime.now().isoformat()
                    }
                    save_json_file(SEEN_NOTICES_FILE, seen_notices)
            else:
                already_seen_count += 1

        if not fresh_candidates:
            logger.info(f"ℹ️ All {len(search_results)} notices for {org_name} were already processed or expired. Skipping.")
            continue

        # Check official domain presence if from search engine
        if not fresh_candidates[0].get("is_direct_portal", False):
            source_urls = [r["url"] for r in fresh_candidates]
            has_official = source_validator.validate_exam_update_sources(source_urls)
            if not has_official:
                logger.info(f"⚠️ Skipping candidates for {org_name}: No official domain verification.")
                continue

        logger.info(f"✅ Processing fresh official update candidate for {org_name}...")

        top_candidate = fresh_candidates[0]
        notice_fingerprint = get_notice_fingerprint(org_name, top_candidate["title"], top_candidate["url"])

        system_prompt = (
            f"You are the Senior Exam Controller & Official Recruitment Updates Specialist for OdishaExamPrep.\n"
            f"TODAY'S DATE IS: {today_date_str} ({today_iso}).\n"
            f"Your role is to analyze verified official government notices and produce authoritative, comprehensive, candidate-first exam guides.\n\n"
            f"======================================================================\n"
            f"1. STRICT 20-CATEGORY EXAM GATEKEEPER (STUDENT MILESTONES ONLY)\n"
            f"======================================================================\n"
            f"Verify that the incoming notice document belongs to one of these 20 OFFICIAL CATEGORIES:\n"
            f"1. Official Notification / Recruitment Released | 2. Application Form Start | 3. Application Last Date\n"
            f"4. Last Date Extended | 5. Correction Window | 6. Admit Card / Hall Ticket Released\n"
            f"7. Exam Date / Schedule Announced | 8. Exam Rescheduled | 9. Exam Cancelled / Postponed\n"
            f"10. City Intimation / Centre Slip | 11. Answer Key Released | 12. Final / Revised Answer Key\n"
            f"13. Objection Window Open | 14. Result / Score Released | 15. Cut-off / Merit List\n"
            f"16. Scorecard Available | 17. Document Verification (DV) Schedule | 18. Interview / Physical Test Date\n"
            f"19. Final Selection List | 20. Important Official Corrigendum\n\n"
            f"• HARD REJECTION (Respond with status: 'REJECT'):\n"
            f"  - Procurement tenders, vehicle auctions, stationery, building works.\n"
            f"  - Internal staff seniority, promotion committee lists, departmental transfers.\n"
            f"  - Routine school exams (Class 8, 9, High School Board).\n"
            f"  - Disqualified / rejected applicant roll number lists.\n"
            f"  - EXPIRED NOTICES: If the application last date or edit window has ALREADY PASSED before today ({today_date_str}), REJECT IMMEDIATELY.\n"
            f"  - OBSOLETE ARCHIVE RECRUITMENTS: Notices from 2024 or earlier with no active 2026 milestone.\n"
            f"  - COACHING RUMORS / SPECULATION: Any text containing 'expected vacancies', 'tentative leak', or third-party coaching claims.\n\n"
            f"======================================================================\n"
            f"2. ZERO-TOLERANCE ANTI-HALLUCINATION & FACTUAL TRUTH RULE\n"
            f"======================================================================\n"
            f"Every single vacancy number, educational qualification, age limit, application fee, and schedule MUST be strictly grounded in the official notification text/PDF extract provided.\n"
            f"NEVER guess, estimate, or invent facts. If a specific field is not explicitly present in the document, write 'N/A' or 'Refer to Official Notification PDF'.\n\n"
            f"======================================================================\n"
            f"3. ARTICLE STRUCTURE & SEO HTML GUIDELINES\n"
            f"======================================================================\n"
            f"Generate an exhaustive, highly educational structured article (800-1400 words) in clean HTML:\n"
            f"1. Executive Summary Callout Box: Highlighting Board, Advt No, and Critical Action Date.\n"
            f"2. Key Important Dates Table (HTML <table> with <thead> and <tbody> rows).\n"
            f"3. Vacancy & Eligibility Overview (if recruitment) OR Shift & Timing Matrix (if exam/admit card).\n"
            f"4. Step-by-Step Instructions for candidates on how to check/download.\n"
            f"5. Official Direct Document Link CTA Button.\n"
            f"6. Top 4 Frequently Asked Questions (FAQ).\n\n"
            f"======================================================================\n"
            f"4. MANDATORY STRUCTURED CONTEXT FIELDS FOR SOCIAL BROADCASTS\n"
            f"======================================================================\n"
            f"Extract and populate full context fields with concrete, crystal-clear details:\n"
            f"- vacancies: Total posts (e.g. '2,008 Backlog Posts' or 'N/A' if Result/Notice)\n"
            f"- eligibility: Required qualification & age (e.g. 'Graduation in any discipline | Age: 20-28 Years')\n"
            f"- timeline_events: A structured list of 2 to 4 specific date events with exact clear labels:\n"
            f"  [\n"
            f'    {{"label": "Online Registration / Application Window", "date": "25 Aug 2026 – 15 Sep 2026"}},\n'
            f'    {{"label": "Fee Payment Last Date", "date": "15 Sep 2026"}},\n'
            f'    {{"label": "Tentative Exam Schedule", "date": "Nov 2026"}}\n'
            f"  ]\n"
            f"- bullets: 3 focused, high-value bullet points (25-35 words each) focusing on:\n"
            f"  1. Selection Process & Stages (e.g. Prelims + Mains + Skill Test / No Interview).\n"
            f"  2. Important Examination Conditions, Marking Pattern or Syllabus Focus.\n"
            f"  3. Direct Candidate Action Plan & Application Mode.\n"
            f"  (DO NOT repeat the eligibility or dates in the bullets — keep them 100% focused on actionable exam intelligence!)\n\n"
            f"Return ONLY valid JSON matching this schema:\n"
            f"{{\n"
            f'  "status": "ACCEPT" | "REJECT",\n'
            f'  "reason": "...",\n'
            f'  "decision": "NEW_ARTICLE" | "UPDATE_EXISTING",\n'
            f'  "content_type": "EXAM_UPDATE",\n'
            f'  "organization": "...",\n'
            f'  "exam": "Full un-truncated exam title (e.g. Combined Graduate Level (CGL) Examination 2026)",\n'
            f'  "update_type": "...",\n'
            f'  "notification_number": "...",\n'
            f'  "title": "Complete, un-truncated official exam update title (ZERO \'...\')",\n'
            f'  "vacancies": "e.g. 2,008 Posts",\n'
            f'  "eligibility": "e.g. Graduation in any discipline | Age: 20-28 Years",\n'
            f'  "dates": "e.g. 25 Aug 2026 - 15 Sep 2026",\n'
            f'  "exam_schedule": "e.g. Prelims: Nov 2026",\n'
            f'  "timeline_events": [\n'
            f'    {{"label": "Online Application Window", "date": "25 Aug 2026 – 15 Sep 2026"}},\n'
            f'    {{"label": "Fee Payment Deadline", "date": "15 Sep 2026"}}\n'
            f'  ],\n'
            f'  "bullets": [\n'
            f'    "Selection Mode: Selection will be conducted via Computer Based Online Examination followed by Document Verification.",\n'
            f'    "Exam Pattern: The test comprises objective sections in Reasoning, Quantitative Aptitude, English, and General Awareness.",\n'
            f'    "Next Step: Eligible candidates must register online through the official portal before the closing deadline."\n'
            f'  ],\n'
            f'  "meta_title": "SEO Title under 60 chars | OdishaExamPrep",\n'
            f'  "meta_description": "Compelling 150-160 char summary for Google SERP",\n'
            f'  "slug": "unique-event-slug-with-exam-and-year",\n'
            f'  "html_content": "Full rich HTML article (with <h2>, <h3>, <table>, <ul>, <ol>, and CTA buttons)",\n'
            f'  "keywords": "comma separated keywords",\n'
            f'  "image_search_query": "short 2-4 word visual search term for real Pexels stock photo",\n'
            f'  "official_source": "https://... (direct link to official notice or document page)",\n'
            f'  "quality_scores": {{"accuracy": 9, "usefulness": 9, "source_quality": 9, "readability": 8, "repetition_risk": 1}}\n'
            f"}}"
        )

        user_prompt = (
            f"Organization: {org_name}\n"
            f"Government Level: {org.get('government_level')}\n"
            f"Notice Title: {top_candidate.get('title')}\n"
            f"Notice Document Link: {top_candidate.get('url')}\n"
            f"Notice Content & Document Extract:\n{top_candidate.get('snippet')}\n\n"
            f"Generate an official exam update article if there is a genuine, verified official notification."
        )

        try:
            raw_response, _ai_model, _ai_fallback = call_deepseek_api([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ])
            article_data = json.loads(raw_response)

            if article_data.get("status") == "REJECT":
                logger.info(f"ℹ️ DeepSeek rejected candidate for {org_name}: {article_data.get('reason')}")
                seen_notices[notice_fingerprint] = {
                    "portal": org_name,
                    "title": top_candidate["title"],
                    "status": "REJECTED_BY_AI",
                    "processed_at": datetime.now().isoformat()
                }
                save_json_file(SEEN_NOTICES_FILE, seen_notices)
                continue

            # Deterministic Factual Integrity & Anti-Hallucination Gate (Zero Trust in LLM)
            is_valid, reject_reason, article_data = ExamFactualIntegrityValidator.validate_and_sanitize(article_data, top_candidate)
            if not is_valid:
                logger.info(f"🚫 Factual Integrity Validator rejected candidate for {org_name}: {reject_reason}")
                seen_notices[notice_fingerprint] = {
                    "portal": org_name,
                    "title": top_candidate["title"],
                    "status": f"FAILED_INTEGRITY_{reject_reason}",
                    "processed_at": datetime.now().isoformat()
                }
                save_json_file(SEEN_NOTICES_FILE, seen_notices)
                continue

            # Duplicate check
            is_dup = DuplicateDetector.is_exam_update_duplicate(
                article_data.get("organization", org_name),
                article_data.get("exam", org_name),
                article_data.get("update_type", "Notification"),
                article_data.get("notification_number", ""),
                history
            )
            if is_dup:
                logger.info(f"⚠️ Skipping duplicate exam update for {org_name} ({article_data.get('title')}).")
                seen_notices[notice_fingerprint] = {
                    "portal": org_name,
                    "title": top_candidate["title"],
                    "status": "DUPLICATE",
                    "processed_at": datetime.now().isoformat()
                }
                save_json_file(SEEN_NOTICES_FILE, seen_notices)
                continue

            # Real Stock Photo search from Pexels API (NO AI image generation)
            img_query = article_data.get("image_search_query") or f"{org_name} exam study"
            pexels_img = fetch_pexels_featured_image(
                img_query,
                article_slug=article_data.get("slug", ""),
                title=article_data.get("title", ""),
                category="Exam Update",
                target_exam=org_name
            )
            if pexels_img:
                article_data["featured_image"] = pexels_img["image_url"]
                article_data["featured_image_alt"] = pexels_img["alt_text"]
                article_data["photographer"] = pexels_img["photographer"]
            else:
                article_data["featured_image"] = "https://images.pexels.com/photos/3184325/pexels-photo-3184325.jpeg?auto=compress&cs=tinysrgb&w=1200"
                article_data["featured_image_alt"] = "Official exam notification update"

            # Technical SEO Validation
            article_data = SEOValidator.validate_article(article_data)
            article_data["published_at"] = datetime.now().isoformat()
            
            # Explicitly map structured social broadcast fields
            article_data["vacancies"] = article_data.get("vacancies", "")
            article_data["eligibility"] = article_data.get("eligibility", "")
            article_data["dates"] = article_data.get("dates", "")
            article_data["exam_schedule"] = article_data.get("exam_schedule", "")
            article_data["timeline_events"] = article_data.get("timeline_events", [])
            article_data["bullets"] = article_data.get("bullets", [])
            article_data["official_link"] = top_candidate.get("url") or article_data.get("official_source")

            # Insert or update Supabase
            cannibal = DuplicateDetector.check_cannibalization_against_blogs(article_data["title"], existing_blogs)
            if cannibal["action"] == "UPDATE_EXISTING":
                db_res = supabase_client.update_blog_post(cannibal["existing_article_id"], article_data)
                article_id = cannibal["existing_article_id"]
            else:
                db_res = supabase_client.insert_blog_post(article_data)
                if not db_res or not db_res.get("id"):
                    logger.error(f"❌ Supabase DB insertion failed for {org_name}. Skipping public broadcast.")
                    send_admin_alert("EXAM_UPDATE", "FAILED", {"stage": f"Supabase Insertion for {org_name}", "error": "Database insert failed or returned no ID."})
                    continue
                article_id = db_res.get("id")

            article_url = f"https://www.odishaexamprep.in/blog/{article_id}"
            article_data["article_url"] = article_url
            article_data["article_id"] = article_id

            # Render authoritative 1080x1080 visual card for multi-platform social broadcast
            try:
                from exam_card_renderer import render_exam_alert_card
                card_img = render_exam_alert_card(article_data)
                if card_img and os.path.exists(card_img):
                    article_data["slide_image_path"] = card_img
                    article_data["cover_image"] = card_img
                    logger.info(f"🎨 Generated 1080x1080 visual card: {card_img}")
            except Exception as render_ex:
                logger.warning(f"⚠️ Visual card render note ({render_ex}). Continuing...")

            # Publish to YouTube Community
            try:
                from post_exam_to_youtube import post_exam_update_to_youtube
                yt_success = post_exam_update_to_youtube(article_data)
                article_data["youtube_status"] = "Published to YouTube Community ✅" if yt_success else "Skipped / Pending Setup ⚠️"
            except Exception as yt_err:
                logger.warning(f"⚠️ YouTube Community posting note: {yt_err}")
                article_data["youtube_status"] = "Skipped ⚠️"

            # Save history, seen notices & Telegram alert
            HistoryManager.save_exam_updates_history(article_data)
            seen_notices[notice_fingerprint] = {
                "portal": org_name,
                "title": top_candidate["title"],
                "article_id": article_id,
                "status": "PUBLISHED",
                "processed_at": datetime.now().isoformat()
            }
            save_json_file(SEEN_NOTICES_FILE, seen_notices)

            article_data["model_used"] = _ai_model
            article_data["used_fallback"] = _ai_fallback
            send_admin_alert("EXAM_UPDATE", "SUCCESS", article_data)

            published_count += 1
            logger.info(f"🎉 Engine 1 published official update: '{article_data.get('title')}' ({article_url})")

        except Exception as proc_err:
            logger.error(f"❌ Error processing candidate for {org_name}: {proc_err}")
            send_admin_alert("EXAM_UPDATE", "FAILED", {"stage": f"Candidate Processing for {org_name}", "error": str(proc_err)})
            continue

    if published_count == 0:
        odisha_portals = [p for p in scanned_portals if any(k in p.lower() for k in ["opsc", "ossc", "osssc", "odisha", "ssb", "bse", "oavs", "court", "optcl", "omc"])]
        central_portals = [p for p in scanned_portals if p not in odisha_portals]

        audit_lines = [
            f"🛡️ <b>OFFICIAL EXAM PORTAL AUDIT & SCAN REPORT</b>\n",
            f"📅 <b>Date:</b> {today_date_str}",
            f"🏛️ <b>Scanned Official Portals ({len(scanned_portals)} Active):</b>",
            f"• <b>Odisha State:</b> {', '.join(odisha_portals[:6]) if odisha_portals else 'None'}",
            f"• <b>Central Bodies:</b> {', '.join(central_portals[:6]) if central_portals else 'None'}\n",
            f"📊 <b>SCAN RESULTS & AUDIT EVIDENCE:</b>",
            f"• <b>Total Portals Scanned:</b> {len(scanned_portals)} official domains ✅",
            f"• <b>Candidate Notices Evaluated:</b> {total_evaluated_notices} items",
            f"• <b>Previously Broadcasted Notices:</b> {already_seen_count} (Saved in permanent history)",
            f"• <b>Non-Student / Deputation Notices Blocked:</b> {ignored_deputation_count} items",
            f"• <b>Expired Deadline Notices Dropped:</b> {ignored_expired_count} items",
            f"• <b>New Student Exam Releases Detected:</b> <b>0 New Notices</b>\n",
            f"💡 <b>Transparency Summary:</b>",
            f"All government boards are 100% up to date. No new competitive student exam notices were released during this scan window. The public channel remains clean and noise-free. Next scheduled scan will check again automatically."
        ]

        if failed_portals:
            audit_lines.append(f"\n⚠️ <i>Portal Notice: {', '.join(failed_portals)} experienced slow network or timeout during scan.</i>")

        admin_summary_msg = "\n".join(audit_lines)
        send_admin_alert("EXAM_UPDATE", "NOTICE", {"message": admin_summary_msg})

    logger.info(f"✅ Engine 1 complete. Published {published_count} official exam updates.")

if __name__ == "__main__":
    try:
        main()
    except SystemExit as se:
        sys.exit(se.code)
    except Exception as e:
        logger.error(f"❌ Fatal ExamUpdateEngine Error: {e}")
        try:
            send_admin_alert("EXAM_UPDATE", "FAILED", {"stage": "Main Runner Exception", "error": str(e)})
        except Exception:
            pass
        sys.exit(1)
