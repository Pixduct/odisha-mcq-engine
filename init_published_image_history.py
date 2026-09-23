import os
import sys
import json
import re
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)

from shared.supabase_client import SupabaseBlogClient

PUBLISHED_HISTORY_PATH = os.path.join(SCRIPT_DIR, "published_image_history.json")

def extract_pexels_id(url_or_string: str) -> str:
    if not url_or_string:
        return ""
    match = re.search(r'pexels-photo-(\d+)|/photos/(\d+)', url_or_string)
    if match:
        return match.group(1) or match.group(2)
    return ""

def main():
    print("[InitPublishedHistory] Scanning existing Supabase blogs to populate automations/published_image_history.json...")

    url = os.getenv("VITE_SUPABASE_URL") or os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

    if not url or not key:
        print("[InitPublishedHistory] Supabase credentials not found.")
        return

    os.environ["SUPABASE_URL"] = url
    os.environ["SUPABASE_KEY"] = key

    client = SupabaseBlogClient()
    blogs = client.fetch_all_blogs()

    history = []
    seen_ids = set()

    for blog in blogs:
        blog_id = blog.get("id", "")
        icon = blog.get("icon", "")
        slug = blog.get("slug", "")
        created = blog.get("createdAt", datetime.now().isoformat())

        photo_id = extract_pexels_id(icon)
        if photo_id and photo_id not in seen_ids:
            seen_ids.add(photo_id)
            history.append({
                "blog_id": blog_id,
                "slug": slug,
                "image_source": "pexels",
                "image_id": photo_id,
                "image_url": icon if photo_id in icon else f"https://images.pexels.com/photos/{photo_id}/pexels-photo-{photo_id}.jpeg",
                "photographer": "Pexels Stock",
                "photographer_url": "https://www.pexels.com",
                "search_query": "academic study",
                "published_at": created
            })

    with open(PUBLISHED_HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump({"images": history}, f, indent=2, ensure_ascii=False)

    print(f"[InitPublishedHistory] Successfully populated automations/published_image_history.json with {len(history)} published image records.")

if __name__ == "__main__":
    main()
