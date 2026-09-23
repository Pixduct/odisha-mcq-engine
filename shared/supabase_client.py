import os
import json
import requests
from typing import Dict, Any, Optional, List

try:
    from dotenv import load_dotenv
    load_dotenv()
    root_env = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")
    if os.path.exists(root_env):
        load_dotenv(root_env)
except Exception:
    pass

SUPABASE_URL = (os.getenv("SUPABASE_URL") or os.getenv("VITE_SUPABASE_URL") or "").rstrip("/")
SUPABASE_KEY = (
    os.getenv("SUPABASE_SERVICE_ROLE_KEY") or
    os.getenv("SUPABASE_KEY") or
    os.getenv("VITE_SUPABASE_ANON_KEY") or
    ""
).strip('"').strip("'")


class SupabaseBlogClient:
    """
    Direct HTTP REST API Client for Supabase Database.
    Operates with zero external SDK dependencies using requests.
    """
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL") or os.getenv("VITE_SUPABASE_URL") or SUPABASE_URL
        self.key = (
            os.getenv("SUPABASE_SERVICE_ROLE_KEY") or
            os.getenv("SUPABASE_KEY") or
            os.getenv("VITE_SUPABASE_ANON_KEY") or
            SUPABASE_KEY
        ).strip('"').strip("'")
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }

    def insert_blog_post(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Inserts article into Supabase 'exams' table with category='blog'.
        Guarantees the actual inserted record with a valid PostgreSQL UUID is returned.
        """
        endpoint = f"{self.url.rstrip('/')}/rest/v1/exams"
        title = data.get("title", "").strip()
        payload = {
            "name": title,
            "description": data.get("html_content", ""),
            "category": "blog",
            "icon": data.get("featured_image", "student 1.png"),
            "metaTitle": data.get("meta_title", title),
            "metaDescription": data.get("meta_description", ""),
            "keywords": data.get("keywords", ""),
            "targetExamId": data.get("targetExamId", None),
            "examDate": data.get("published_at", None),
            "createdAt": data.get("published_at", None)
        }

        try:
            res = requests.post(endpoint, headers=self.headers, json=payload, timeout=20)
            if res.ok:
                try:
                    items = res.json()
                    if isinstance(items, list) and len(items) > 0 and items[0].get("id"):
                        return items[0]
                    elif isinstance(items, dict) and items.get("id"):
                        return items
                except Exception:
                    pass
            else:
                print(f"[SupabaseClient] ⚠️ Insert blog HTTP response ({res.status_code}): {res.text}")
        except Exception as e:
            print(f"[SupabaseClient] ❌ HTTP error inserting blog: {e}")

        # Fallback: Query Supabase immediately by title to fetch the true inserted UUID
        try:
            query_url = f"{self.url.rstrip('/')}/rest/v1/exams?category=eq.blog&name=eq.{requests.utils.quote(title)}&select=*&order=createdAt.desc&limit=1"
            q_res = requests.get(query_url, headers=self.headers, timeout=15)
            if q_res.ok:
                rows = q_res.json()
                if rows and len(rows) > 0 and rows[0].get("id"):
                    print(f"[SupabaseClient] ✅ Retrieved newly inserted blog ID from DB: {rows[0]['id']}")
                    return rows[0]
        except Exception as q_err:
            print(f"[SupabaseClient] ⚠️ Fallback query error: {q_err}")

        return None

    def update_blog_post(self, existing_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Updates an existing article in Supabase 'exams' table by ID.
        """
        endpoint = f"{self.url.rstrip('/')}/rest/v1/exams?id=eq.{existing_id}"
        payload = {
            "name": data.get("title", ""),
            "description": data.get("html_content", ""),
            "icon": data.get("featured_image", "student 1.png"),
            "metaTitle": data.get("meta_title", data.get("title", "")),
            "metaDescription": data.get("meta_description", ""),
            "keywords": data.get("keywords", ""),
            "targetExamId": data.get("targetExamId", None),
            "examDate": data.get("published_at", None)
        }

        try:
            res = requests.patch(endpoint, headers=self.headers, json=payload, timeout=20)
            if res.ok:
                try:
                    items = res.json()
                    if isinstance(items, list) and len(items) > 0:
                        return items[0]
                    elif isinstance(items, dict):
                        return items
                except Exception:
                    pass
                return {"id": existing_id, **payload}
            else:
                print(f"[SupabaseClient] ⚠️ Update blog error ({res.status_code}): {res.text}")
        except Exception as e:
            print(f"[SupabaseClient] ❌ HTTP error updating blog: {e}")
        return None

    def fetch_all_blogs(self) -> List[Dict[str, Any]]:
        endpoint = f"{self.url.rstrip('/')}/rest/v1/exams?category=eq.blog&select=*"
        try:
            res = requests.get(endpoint, headers=self.headers, timeout=20)
            if res.ok:
                return res.json() or []
        except Exception as e:
            print(f"[SupabaseClient] ⚠️ Error fetching blogs: {e}")
        return []

    def fetch_all_current_affairs(self) -> List[Dict[str, Any]]:
        endpoint = f"{self.url.rstrip('/')}/rest/v1/exams?category=eq.current_affairs&select=*"
        try:
            res = requests.get(endpoint, headers=self.headers, timeout=20)
            if res.ok:
                return res.json() or []
        except Exception as e:
            print(f"[SupabaseClient] ⚠️ Error fetching current affairs: {e}")
        return []

    def insert_current_affairs(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Inserts 360° Current Affairs Digest into Supabase 'exams' table with category='current_affairs'.
        """
        endpoint = f"{self.url.rstrip('/')}/rest/v1/exams"
        mcqs_json_str = json.dumps(data.get("mcqs", []))
        full_rich_description = (
            f"{data.get('full_context', '')}\n"
            f"{data.get('static_gk_pointers', '')}\n"
            f"{data.get('data_table_html', '')}\n"
            f"<!--MCQ_JSON:{mcqs_json_str}-->"
        )

        icon_val = data.get("image_url") or data.get("featured_image") or "student 1.png"
        if isinstance(icon_val, dict):
            icon_val = icon_val.get("image_url") or "student 1.png"
        icon_val = str(icon_val).strip() or "student 1.png"

        payload = {
            "name": data.get("title", ""),
            "description": full_rich_description,
            "category": "current_affairs",
            "icon": icon_val,
            "metaTitle": f"{data.get('category')} Current Affairs: {data.get('title')}",
            "metaDescription": data.get("summary", ""),
            "keywords": f"current affairs, {data.get('category')}, odisha exam prep",
            "targetExamId": data.get("category", "General"),
            "examDate": data.get("event_date", None),
            "createdAt": data.get("published_at", None)
        }

        try:
            res = requests.post(endpoint, headers=self.headers, json=payload, timeout=20)
            if res.ok:
                items = res.json()
                print(f"[SupabaseClient] ✅ Inserted Current Affairs article into DB: '{data.get('title')}'")
                return items[0] if isinstance(items, list) and items else {"status": "ok"}
            else:
                print(f"[SupabaseClient] ❌ Insert CA error ({res.status_code}): {res.text}")
        except Exception as e:
            print(f"[SupabaseClient] ❌ HTTP error inserting CA: {e}")

        return None
