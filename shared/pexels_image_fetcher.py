import os
import json
import re
import requests
from datetime import datetime
from typing import Dict, Any, Optional, List

from shared.wikimedia_fetcher import fetch_wikimedia_image
from shared.exam_visual_context import build_smart_exam_visual_query, infer_exam_visual_context
from shared.landmark_image_registry import resolve_real_landmark_image

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
PUBLISHED_IMAGE_HISTORY_PATH = os.path.join(PROJECT_ROOT, "published_image_history.json")

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")
IMAGE_REUSE_COOLDOWN = int(os.getenv("IMAGE_REUSE_COOLDOWN", "30"))

# IRRELEVANT HOME DECOR, VINTAGE, AND VECTOR NEGATIVE KEYWORDS
NEGATIVE_KEYWORDS = [
    "furniture", "cabinet", "interior", "living room", "sofa", "couch",
    "decoration", "decor", "coffee table", "facade", "building", "architecture",
    "lawn", "park bench", "house", "apartment", "kitchen", "bedroom", "armchair",
    "vintage", "antique", "black and white", "grayscale", "monochrome", "retro",
    "1920s", "1930s", "1940s", "1950s", "historic classroom", "old school", "drawing", "illustration", "cartoon", "vector"
]

# HAND-CURATED VERIFIED MODERN ACADEMIC & PROFESSION STOCK PHOTOS
VERIFIED_READING_ENGLISH_PHOTOS = [
    {"id": "3184325", "url": "https://images.pexels.com/photos/3184325/pexels-photo-3184325.jpeg?auto=compress&cs=tinysrgb&w=1200", "alt": "Student reading and highlighting study notes in modern library", "photographer": "Pexels Stock"},
    {"id": "5905709", "url": "https://images.pexels.com/photos/5905709/pexels-photo-5905709.jpeg?auto=compress&cs=tinysrgb&w=1200", "alt": "Focused candidate analyzing reading comprehension passage notes", "photographer": "Pexels Stock"},
    {"id": "4144923", "url": "https://images.pexels.com/photos/4144923/pexels-photo-4144923.jpeg?auto=compress&cs=tinysrgb&w=1200", "alt": "Student studying English grammar and verbal ability textbook", "photographer": "Pexels Stock"},
    {"id": "159711", "url": "https://images.pexels.com/photos/159711/books-bookstore-book-reading-159711.jpeg?auto=compress&cs=tinysrgb&w=1200", "alt": "Modern library bookshelves and open study books", "photographer": "Pexels Stock"}
]

VERIFIED_MATH_REASONING_PHOTOS = [
    {"id": "5905712", "url": "https://images.pexels.com/photos/5905712/pexels-photo-5905712.jpeg?auto=compress&cs=tinysrgb&w=1200", "alt": "Candidate solving quantitative aptitude calculations with pen and notebook", "photographer": "Pexels Stock"},
    {"id": "5900777", "url": "https://images.pexels.com/photos/5900777/pexels-photo-5900777.jpeg?auto=compress&cs=tinysrgb&w=1200", "alt": "Student solving analytical reasoning problem paper at study desk", "photographer": "Pexels Stock"},
    {"id": "6238050", "url": "https://images.pexels.com/photos/6238050/pexels-photo-6238050.jpeg?auto=compress&cs=tinysrgb&w=1200", "alt": "Mathematical formulas, algebra equations and clean notebook on desk", "photographer": "Pexels Stock"}
]

VERIFIED_POLITY_GOVERNANCE_PHOTOS = [
    {"id": "5668473", "url": "https://images.pexels.com/photos/5668473/pexels-photo-5668473.jpeg?auto=compress&cs=tinysrgb&w=1200", "alt": "Indian constitution and law reference books with wooden gavel in library", "photographer": "Pexels Stock"},
    {"id": "6077326", "url": "https://images.pexels.com/photos/6077326/pexels-photo-6077326.jpeg?auto=compress&cs=tinysrgb&w=1200", "alt": "Legal justice scale, constitution law book and notes on wooden desk", "photographer": "Pexels Stock"}
]

VERIFIED_EXAM_NOTIFICATION_PHOTOS = [
    {"id": "7092613", "url": "https://images.pexels.com/photos/7092613/pexels-photo-7092613.jpeg?auto=compress&cs=tinysrgb&w=1200", "alt": "Candidates writing competitive examination in modern exam hall", "photographer": "Pexels Stock"},
    {"id": "3184325", "url": "https://images.pexels.com/photos/3184325/pexels-photo-3184325.jpeg?auto=compress&cs=tinysrgb&w=1200", "alt": "Government exam candidate checking admit card and notification schedule", "photographer": "Pexels Stock"},
    {"id": "5905712", "url": "https://images.pexels.com/photos/5905712/pexels-photo-5905712.jpeg?auto=compress&cs=tinysrgb&w=1200", "alt": "Student taking practice test paper on examination desk", "photographer": "Pexels Stock"}
]

VERIFIED_NURSING_PHOTOS = [
    {"id": "7972350", "url": "https://images.pexels.com/photos/7972350/pexels-photo-7972350.jpeg?auto=compress&cs=tinysrgb&w=1200", "alt": "Nursing student studying clinical pharmacology textbooks", "photographer": "Pexels Stock"},
    {"id": "5428836", "url": "https://images.pexels.com/photos/5428836/pexels-photo-5428836.jpeg?auto=compress&cs=tinysrgb&w=1200", "alt": "Healthcare candidate reviewing medical diagrams and textbook at study desk", "photographer": "Pexels Stock"}
]

VERIFIED_ENGINEERING_PHOTOS = [
    {"id": "1181671", "url": "https://images.pexels.com/photos/1181671/pexels-photo-1181671.jpeg?auto=compress&cs=tinysrgb&w=1200", "alt": "Engineering student studying technical diagrams and reference manuals", "photographer": "Pexels Stock"},
    {"id": "3861969", "url": "https://images.pexels.com/photos/3861969/pexels-photo-3861969.jpeg?auto=compress&cs=tinysrgb&w=1200", "alt": "Technical aspirant revising engineering study notes", "photographer": "Pexels Stock"}
]

VERIFIED_CGL_GOVT_PHOTOS = [
    {"id": "5900777", "url": "https://images.pexels.com/photos/5900777/pexels-photo-5900777.jpeg?auto=compress&cs=tinysrgb&w=1200", "alt": "Competitive exam student writing notes with pen and paper", "photographer": "Pexels Stock"},
    {"id": "5905709", "url": "https://images.pexels.com/photos/5905709/pexels-photo-5905709.jpeg?auto=compress&cs=tinysrgb&w=1200", "alt": "Student highlighting key points in revision notebook", "photographer": "Pexels Stock"},
    {"id": "3184325", "url": "https://images.pexels.com/photos/3184325/pexels-photo-3184325.jpeg?auto=compress&cs=tinysrgb&w=1200", "alt": "Focused candidate studying exam preparation material at library desk", "photographer": "Pexels Stock"}
]

def load_published_image_history() -> List[Dict[str, Any]]:
    if os.path.exists(PUBLISHED_IMAGE_HISTORY_PATH):
        try:
            with open(PUBLISHED_IMAGE_HISTORY_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("images", []) if isinstance(data, dict) else data
        except Exception:
            return []
    return []

def record_published_image(blog_id: str, slug: str, exam: str, content_type: str, image_source: str, image_id: str, image_url: str, photographer: str, photographer_url: str, search_query: str, visual_context: str):
    os.makedirs(os.path.dirname(PUBLISHED_IMAGE_HISTORY_PATH), exist_ok=True)
    history = load_published_image_history()
    entry = {
        "blog_id": blog_id,
        "slug": slug,
        "exam": exam,
        "content_type": content_type,
        "image_source": image_source,
        "image_id": str(image_id),
        "image_url": image_url,
        "photographer": photographer,
        "photographer_url": photographer_url,
        "search_query": search_query,
        "visual_context": visual_context,
        "published_at": datetime.now().isoformat()
    }
    history.append(entry)
    with open(PUBLISHED_IMAGE_HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump({"images": history}, f, indent=2, ensure_ascii=False)

def fetch_pexels_featured_image(search_query: str, article_slug: str = "", title: str = "", category: str = "", target_exam: str = "", blog_id: str = "", content_type: str = "EVERGREEN_EDUCATIONAL") -> Optional[Dict[str, Any]]:
    """
    Workflow 5 Smart Exam Visual Context Image Engine.
    Combines Real Landmark Registry + Wikimedia Commons + Pexels Stock.
    """
    history = load_published_image_history()
    used_ids = {str(item.get("image_id")) for item in history if item.get("image_id")}
    prev_image_id = str(history[-1].get("image_id")) if history else ""

    # STEP 0: Check Real Geographical Landmark & Institutional Entity Registry
    landmark_res = resolve_real_landmark_image(title or search_query, target_exam or category)
    if landmark_res:
        print(f"[ExamVisualEngine] 🎯 MATCHED REAL LANDMARK PHOTOGRAPH: {landmark_res['search_query']}")
        return landmark_res

    # Build Exam Visual Context Query
    visual_info = build_smart_exam_visual_query(title or search_query, category, target_exam, content_type)
    queries = visual_info["search_queries"]
    primary_query = visual_info["primary_query"]
    avoid_kws = visual_info["avoid_keywords"] + NEGATIVE_KEYWORDS

    print(f"[ExamVisualEngine] Exam: '{target_exam}' | Primary Query: '{primary_query}' | Avoid KWs: {avoid_kws[:4]}")

    selected_candidate = None

    # STEP 1: Search Pexels API
    if PEXELS_API_KEY:
        headers = {"Authorization": PEXELS_API_KEY}
        candidate_pool = []

        for q in queries:
            url = f"https://api.pexels.com/v1/search?query={q.strip().lower()}&orientation=landscape&per_page=15"
            try:
                res = requests.get(url, headers=headers, timeout=12)
                if res.ok:
                    photos = res.json().get("photos", [])
                    for p in photos:
                        pid = str(p.get("id"))
                        alt_desc = (p.get("alt") or "").lower()
                        
                        # Negative Keyword Filter (Hard Rejection)
                        if any(neg in alt_desc for neg in avoid_kws):
                            continue

                        if pid not in used_ids and pid != prev_image_id:
                            candidate_pool.append((p, q))
            except Exception as e:
                print(f"[ExamVisualEngine] Pexels API Error for query '{q}': {e}")

        # Multi-Criteria Scoring (Exam match 25, Article match 30, Profession match 20, Activity match 15, Quality 5, Uniqueness 5)
        best_score = -1
        for photo, q in candidate_pool:
            pid = str(photo.get("id"))
            alt_desc = (photo.get("alt") or "").lower()
            width = photo.get("width", 0)
            height = photo.get("height", 0)

            score = 0
            # 1. Exam & Profession Match (45 pts)
            for ctx_kw in visual_info["primary_context"]:
                if ctx_kw in alt_desc or ctx_kw in q:
                    score += 15
                    break
            
            # 2. Activity & Subject Match (35 pts)
            if any(act in alt_desc for act in ["study", "test", "exam", "note", "paper", "read", "book", "solving"]):
                score += 35

            # 3. Quality & Landscape Aspect Ratio (10 pts)
            if width >= height:
                score += 5
            if width >= 1200:
                score += 5

            # 4. Uniqueness (10 pts)
            if pid not in used_ids:
                score += 10

            if score >= 70 and score > best_score:
                best_score = score
                src = photo.get("src", {})
                img_url = src.get("large2x") or src.get("large") or src.get("original")
                if img_url:
                    selected_candidate = {
                        "image_source": "pexels",
                        "image_id": pid,
                        "image_url": img_url,
                        "alt_text": photo.get("alt") or f"{title} - {target_exam} preparation",
                        "photographer": photo.get("photographer", "Pexels Stock"),
                        "photographer_url": photo.get("photographer_url", "https://www.pexels.com"),
                        "search_query": q
                    }

    # STEP 2: Wikimedia Commons API Fallback
    if not selected_candidate:
        print("[ExamVisualEngine] Pexels candidate score < 70 or unavailable. Trying Wikimedia Commons API...")
        for q in queries[:2]:
            wiki_res = fetch_wikimedia_image(q, used_ids)
            if wiki_res:
                selected_candidate = wiki_res
                selected_candidate["search_query"] = q
                print(f"[ExamVisualEngine] Selected Wikimedia Commons Image ({wiki_res['license']}): {wiki_res['image_url']}")
                break

    # STEP 3: Verified Modern Concept-Aligned Academic Photo Fallback
    if not selected_candidate:
        print(f"[ExamVisualEngine] Selecting from Verified Modern Academic Stock Directory for '{target_exam}' / '{title[:35]}'...")
        ctx_info = infer_exam_visual_context(target_exam, title, category)
        primary_kws = ctx_info.get("primary_context", [])
        combined_text = f"{target_exam} {title} {category}".lower()

        target_pool = VERIFIED_CGL_GOVT_PHOTOS
        if any(k in combined_text for k in ["read", "comprehension", "english", "grammar", "verbal", "skimming", "tone"]):
            target_pool = VERIFIED_READING_ENGLISH_PHOTOS
        elif any(k in combined_text for k in ["math", "quant", "reasoning", "algebra", "puzzle", "calculation", "arithmetic"]):
            target_pool = VERIFIED_MATH_REASONING_PHOTOS
        elif any(k in combined_text for k in ["polity", "constitution", "law", "judiciary", "article", "governance"]):
            target_pool = VERIFIED_POLITY_GOVERNANCE_PHOTOS
        elif any(k in combined_text for k in ["notification", "admit card", "exam date", "result", "schedule", "cgl", "recruitment"]):
            target_pool = VERIFIED_EXAM_NOTIFICATION_PHOTOS
        elif "nursing" in primary_kws or "healthcare" in primary_kws or "medical" in combined_text:
            target_pool = VERIFIED_NURSING_PHOTOS
        elif "engineering" in primary_kws or "technical" in primary_kws or "ctsre" in combined_text:
            target_pool = VERIFIED_ENGINEERING_PHOTOS

        for item in target_pool:
            pid = str(item["id"])
            if pid not in used_ids and pid != prev_image_id:
                selected_candidate = {
                    "image_source": "pexels",
                    "image_id": pid,
                    "image_url": item["url"],
                    "alt_text": item["alt"],
                    "photographer": item["photographer"],
                    "photographer_url": "https://www.pexels.com",
                    "search_query": primary_query
                }
                break

        if not selected_candidate and target_pool:
            item = target_pool[0]
            selected_candidate = {
                "image_source": "pexels",
                "image_id": str(item["id"]),
                "image_url": item["url"],
                "alt_text": item["alt"],
                "photographer": item["photographer"],
                "photographer_url": "https://www.pexels.com",
                "search_query": primary_query
            }

    if selected_candidate:
        pid = selected_candidate["image_id"]
        img_url = selected_candidate["image_url"]
        record_published_image(
            blog_id=blog_id or "pending-id",
            slug=article_slug,
            exam=target_exam,
            content_type=content_type,
            image_source=selected_candidate.get("image_source", "pexels"),
            image_id=pid,
            image_url=img_url,
            photographer=selected_candidate.get("photographer", "Pexels Stock"),
            photographer_url=selected_candidate.get("photographer_url", "https://www.pexels.com"),
            search_query=selected_candidate.get("search_query", primary_query),
            visual_context=", ".join(visual_info["primary_context"])
        )
        print(f"[ExamVisualEngine] SUCCESS! Selected/Generated Exam Image ({selected_candidate.get('image_source')}) ID {pid} by {selected_candidate.get('photographer')}.")
        return selected_candidate
    else:
        print("[ExamVisualEngine] IMAGE_NOT_FOUND: Safely publishing article without hero image.")
        return None
