import requests
import re
from typing import Dict, Any, Optional

def fetch_wikimedia_image(search_query: str, used_ids: set) -> Optional[Dict[str, Any]]:
    """
    Searches Wikimedia Commons API for relevant open-licensed photographs (CC BY / Public Domain).
    Verifies licensing information and author attribution.
    """
    clean_query = search_query.strip().lower()[:60]
    api_url = "https://commons.wikimedia.org/w/api.php"
    
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": f"file:{clean_query}",
        "gsrnamespace": 6,  # File namespace
        "prop": "imageinfo",
        "iiprop": "url|extmetadata|mime",
        "gsrlimit": 10,
        "format": "json"
    }
    
    headers = {"User-Agent": "OdishaExamPrep/1.0 (https://www.odishaexamprep.in; admin@odishaexamprep.in)"}
    
    try:
        res = requests.get(api_url, params=params, headers=headers, timeout=12)
        if not res.ok:
            return None
            
        data = res.json()
        pages = data.get("query", {}).get("pages", {})
        
        for page_id, page in pages.items():
            imageinfo = page.get("imageinfo", [{}])[0]
            mime = imageinfo.get("mime", "")
            
            # Allow only JPEG/PNG images
            if not mime.startswith("image/"):
                continue
                
            img_url = imageinfo.get("url")
            description_url = imageinfo.get("descriptionurl")
            extmeta = imageinfo.get("extmetadata", {})
            
            license_name = extmeta.get("LicenseShortName", {}).get("value", "Public Domain")
            author_raw = extmeta.get("Artist", {}).get("value", "Wikimedia Contributor")
            
            # Clean author HTML string
            author = re.sub(r'<[^>]*>', '', author_raw).strip() or "Wikimedia Contributor"
            license_url = extmeta.get("LicenseUrl", {}).get("value", "https://creativecommons.org/licenses/publicdomain/")
            
            wiki_id = f"wiki_{page_id}"
            if wiki_id in used_ids:
                continue

            # Verify acceptable open license (Public Domain, CC BY, CC BY-SA)
            lic_lower = license_name.lower()
            if any(ok in lic_lower for ok in ["public domain", "cc by", "cc-by", "pd", "gfdl"]):
                return {
                    "image_source": "wikimedia",
                    "image_id": wiki_id,
                    "image_url": img_url,
                    "source_url": description_url,
                    "author": author,
                    "license": license_name,
                    "license_url": license_url,
                    "photographer": author,
                    "photographer_url": description_url,
                    "alt_text": f"Wikimedia Commons image for {search_query}"
                }
    except Exception as e:
        print(f"[WikimediaFetcher] Error fetching Wikimedia Commons image: {e}")
        
    return None
