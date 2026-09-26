import os
import re
import io
import time
import requests
from typing import Optional, Dict, Any

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def extract_google_drive_file_id(url: str) -> Optional[str]:
    """
    Extracts the unique file ID from any variation of Google Drive share URL:
    - https://drive.google.com/file/d/1A2B3C4D5E/view?usp=sharing
    - https://drive.google.com/open?id=1A2B3C4D5E
    - https://drive.google.com/uc?id=1A2B3C4D5E
    """
    if not url or "drive.google.com" not in url:
        return None

    # Match /file/d/<ID>
    m1 = re.search(r'/file/d/([a-zA-Z0-9_-]+)', url)
    if m1:
        return m1.group(1)

    # Match id=<ID>
    m2 = re.search(r'[?&]id=([a-zA-Z0-9_-]+)', url)
    if m2:
        return m2.group(1)

    return None

def convert_google_drive_to_direct_url(url: str) -> str:
    """
    Converts a Google Drive view/share URL to a high-resolution direct download/stream link.
    """
    file_id = extract_google_drive_file_id(url)
    if file_id:
        return f"https://drive.google.com/uc?export=download&id={file_id}"
    return url

def download_and_sanitize_image(image_url: str, output_filename: str = "custom_blog_cover.png") -> Optional[str]:
    """
    Downloads custom image from Google Drive, Unsplash, or direct HTTP URL,
    validates the image binary, saves it locally, and returns the local file path.
    """
    if not image_url or not str(image_url).strip():
        return None

    clean_url = str(image_url).strip()
    file_id = extract_google_drive_file_id(clean_url)
    output_path = os.path.join(SCRIPT_DIR, output_filename)

    candidate_urls = []
    if file_id:
        candidate_urls = [
            f"https://lh3.googleusercontent.com/d/{file_id}=w1200",
            f"https://drive.usercontent.google.com/download?id={file_id}&export=download",
            f"https://drive.google.com/thumbnail?id={file_id}&sz=w1200",
            f"https://drive.google.com/uc?export=download&id={file_id}"
        ]
    else:
        candidate_urls = [clean_url]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    session = requests.Session()
    for direct_url in candidate_urls:
        try:
            res = session.get(direct_url, headers=headers, timeout=25, allow_redirects=True)
            if "drive.google.com" in direct_url and "confirm=" not in direct_url:
                for k, v in session.cookies.items():
                    if k.startswith("download_warning"):
                        confirm_url = f"{direct_url}&confirm={v}"
                        res = session.get(confirm_url, headers=headers, timeout=25)
                        break

            if res.ok and len(res.content) > 1000 and "text/html" not in res.headers.get("Content-Type", "").lower():
                with open(output_path, "wb") as f:
                    f.write(res.content)
                print(f"[Image Sanitizer] Successfully downloaded custom image ({len(res.content)} bytes) -> {output_path}")
                return output_path
        except Exception as e:
            continue

    print(f"[Image Sanitizer] Notice: Could not download direct binary from {clean_url}. Using vector fallback.")
    return None

def resolve_editorial_image(
    image_url_input: Optional[str],
    title: str,
    category: str,
    target_exam: str,
    slug: str
) -> Dict[str, Any]:
    """
    Resolves the final featured image for a blog article:
    1. If user provided a custom URL in Google Sheet -> Sanitizes & caches the custom image.
    2. If no URL provided -> Generates an official, high-resolution 1200x630 vector graphic banner.
    GUARANTEES ZERO CHOPSTICKS / RANDOM STOCK PHOTOS.
    """
    if image_url_input and str(image_url_input).strip():
        custom_url = str(image_url_input).strip()
        local_img = download_and_sanitize_image(custom_url, f"cover_{slug[:30]}.png")
        if local_img and os.path.exists(local_img):
            return {
                "image_url": custom_url,
                "local_path": local_img,
                "alt_text": title,
                "photographer": "Editorial Team / Custom Upload",
                "is_custom": True
            }

    # Fallback to Intelligent Gemini Imagen / Official Board Vector Banner
    from shared.imagen_generator import generate_blog_imagen_banner
    banner_data = generate_blog_imagen_banner(
        title=title,
        organization=target_exam or category,
        category=category,
        slug=slug
    )

    return {
        "image_url": banner_data["image_url"],
        "local_path": banner_data.get("local_path"),
        "alt_text": banner_data.get("alt_text", title),
        "photographer": banner_data.get("photographer", "Google Gemini AI / Official Banner"),
        "is_custom": False
    }
