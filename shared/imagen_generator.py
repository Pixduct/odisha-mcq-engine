import os
import sys
import re
import json
import base64
import requests
from typing import Dict, Any, Optional

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# Dual-environment path resolution: local monorepo vs standalone GitHub Actions runner
parent_public = os.path.join(os.path.dirname(PROJECT_ROOT), "public")
if os.path.exists(parent_public):
    COVERS_DIR = os.path.join(parent_public, "blog_covers")
else:
    COVERS_DIR = os.path.join(PROJECT_ROOT, "public", "blog_covers")

os.makedirs(COVERS_DIR, exist_ok=True)

def get_gemini_api_key() -> Optional[str]:
    """Retrieves GEMINI_API_KEY from environment."""
    key = os.getenv("GEMINI_API_KEY") or os.getenv("VITE_GEMINI_API_KEY")
    if key and len(key.strip()) > 10:
        return key.strip()
    return None

def synthesize_ai_art_prompt(
    title: str,
    organization: str = "",
    category: str = "",
    context_summary: str = "",
    api_key: str = ""
) -> str:
    """
    Acts as an AI Art Director: Uses Gemini 3.8 Flash to analyze blog context
    and synthesize a tailored, culturally authentic Indian exam/administrative visual prompt.
    """
    system_instruction = (
        "You are an expert visual Art Director for OdishaExamPrep, an Indian competitive examination "
        "and government portal. Your job is to formulate a single, highly detailed, photorealistic prompt "
        "for an AI text-to-image generator (16:9 widescreen composition).\n\n"
        "RULES:\n"
        "1. Setting & Authenticity: MUST reflect authentic Indian government, judicial, administrative, "
        "or university examination contexts (e.g. Orissa High Court courtroom/corridor with Ashok pillar seal, "
        "OPSC/OSSSC administrative secretariat desk with government files, civil service aspirants studying in a quiet modern library, "
        "official state notification desk with fountain pen and stamp).\n"
        "2. Strict Negatives: NEVER use western classrooms, green chalkboards, children, graduation caps, "
        "cartoons, anime, 3D renders, or casual western tropes.\n"
        "3. Aesthetics: Photorealistic, cinematic lighting, 8k resolution, documentary photography, professional architectural and editorial style.\n"
        "4. No Text: Do NOT ask for any letters, words, or text inside the image.\n"
        "Output ONLY the prompt text, nothing else."
    )

    user_content = (
        f"Article Title: {title}\n"
        f"Organization / Commission: {organization or 'Odisha Government'}\n"
        f"Category: {category or 'Government Exam Update'}\n"
        f"Context Details: {context_summary[:300] if context_summary else 'Official government examination and recruitment notice in Odisha.'}\n\n"
        f"Formulate the ideal 16:9 photorealistic image generation prompt:"
    )

    models_to_try = ["gemini-3.8-flash", "gemini-flash-latest", "gemini-3.5-flash-lite"]
    for model in models_to_try:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            payload = {
                "contents": [
                    {"role": "user", "parts": [{"text": f"{system_instruction}\n\n{user_content}"}]}
                ],
                "generationConfig": {
                    "temperature": 0.4,
                    "maxOutputTokens": 300
                }
            }
            res = requests.post(url, json=payload, timeout=20)
            if res.status_code == 200:
                data = res.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    for part in parts:
                        text = part.get("text", "").strip()
                        if text:
                            # Clean up quotes if wrapped
                            clean = text.strip('"\'')
                            return clean
        except Exception as e:
            continue

    # Fallback default prompt if Art Director API fails
    org_clean = organization or "Odisha State Government"
    return (
        f"Photorealistic 16:9 editorial photograph of a dignified Indian government administrative office, "
        f"dedicated to {org_clean}. Polished wooden executive desk with official files, Ashoka Lion Capital emblem, "
        f"brass scales of justice and fountain pen in foreground, soft morning sunlight through architectural windows, "
        f"cinematic lighting, ultra-realistic documentary photography."
    )

def request_gemini_image_generation(prompt: str, api_key: str) -> Optional[bytes]:
    """
    Attempts image generation via Gemini multimodal image generation models:
    gemini-3.1-flash-image and gemini-2.5-flash-image.
    Returns raw image bytes if successful, None otherwise.
    """
    image_models = ["gemini-3.1-flash-image", "gemini-2.5-flash-image"]
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": f"Generate a photorealistic 16:9 widescreen image: {prompt}"}
                ]
            }
        ]
    }

    for model in image_models:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            res = requests.post(url, json=payload, timeout=30)
            if res.status_code == 200:
                data = res.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    for part in parts:
                        inline_data = part.get("inlineData")
                        if inline_data and "data" in inline_data:
                            b64_data = inline_data["data"]
                            img_bytes = base64.b64decode(b64_data)
                            print(f"[Gemini Imagen] Successfully generated image via {model} ({len(img_bytes)} bytes)")
                            return img_bytes
            elif res.status_code == 429:
                # Quota exceeded on free tier (limit: 0 until billing enabled)
                print(f"[Gemini Imagen] Notice: Model {model} returned 429 (Requires Google AI Studio billing/tier).")
            else:
                print(f"[Gemini Imagen] Model {model} returned HTTP {res.status_code}: {res.text[:120]}")
        except Exception as e:
            print(f"[Gemini Imagen] Error calling {model}: {e}")

    return None

def upload_to_supabase_storage(file_path: str, filename: str) -> Optional[str]:
    """Optionally uploads image to Supabase Storage bucket 'blog-covers' if credentials present."""
    supabase_url = os.getenv("VITE_SUPABASE_URL") or os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("VITE_SUPABASE_ANON_KEY")

    if not supabase_url or not service_key:
        return None

    try:
        clean_url = supabase_url.rstrip("/")
        upload_url = f"{clean_url}/storage/v1/object/blog-covers/{filename}"
        headers = {
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "image/jpeg",
            "x-upsert": "true"
        }
        with open(file_path, "rb") as f:
            file_bytes = f.read()

        res = requests.post(upload_url, headers=headers, data=file_bytes, timeout=20)
        if res.status_code in [200, 201]:
            public_cdn_url = f"{clean_url}/storage/v1/object/public/blog-covers/{filename}"
            print(f"[Gemini Imagen] Uploaded to Supabase CDN: {public_cdn_url}")
            return public_cdn_url
    except Exception as e:
        print(f"[Gemini Imagen] Supabase upload error (non-fatal): {e}")

    return None

def generate_blog_imagen_banner(
    title: str,
    organization: str = "",
    category: str = "",
    context_summary: str = "",
    slug: str = ""
) -> Dict[str, Any]:
    """
    Main entry point for intelligent, context-aware blog cover image generation:
    1. Evaluates Gemini Art Director prompt based on blog context.
    2. Requests image generation from Gemini Imagen/Flash Image models.
    3. Saves locally and optionally uploads to Supabase CDN.
    4. Seamlessly falls back to official verified exam board vector banner if Gemini Image quota is not enabled.
    GUARANTEES ZERO MISMATCHED STOCK PHOTOS.
    """
    api_key = get_gemini_api_key()
    safe_slug = re.sub(r'[^a-z0-9]+', '-', (slug or title).lower()).strip('-')[:50]

    if api_key:
        print(f"[Gemini Imagen] Synthesizing intelligent Art Director prompt for '{title[:45]}...'")
        art_prompt = synthesize_ai_art_prompt(
            title=title,
            organization=organization,
            category=category,
            context_summary=context_summary,
            api_key=api_key
        )
        print(f"[Gemini Imagen] Generated Visual Prompt: {art_prompt[:120]}...")

        # Request image generation
        img_bytes = request_gemini_image_generation(art_prompt, api_key)
        if img_bytes:
            filename = f"ai_{safe_slug}.jpg"
            file_path = os.path.join(COVERS_DIR, filename)
            with open(file_path, "wb") as f:
                f.write(img_bytes)

            cdn_url = upload_to_supabase_storage(file_path, filename)
            image_url = cdn_url or f"https://www.odishaexamprep.in/blog_covers/{filename}"

            return {
                "image_url": image_url,
                "alt_text": f"{title} - Official Update Visual",
                "local_path": file_path,
                "photographer": "Google Gemini Imagen AI",
                "is_ai_generated": True
            }

    # Fallback: Official Board Branded Vector Banner (100% Authentic, zero stock photo clichés)
    print(f"[Gemini Imagen] Using official exam board vector banner fallback for '{organization or 'General'}'.")
    from shared.exam_logo_registry import generate_exam_vector_banner
    banner_data = generate_exam_vector_banner(
        title=title,
        target_exam=organization or category,
        update_type=category,
        slug=slug
    )

    return {
        "image_url": banner_data["image_url"],
        "alt_text": banner_data["alt_text"],
        "local_path": banner_data.get("local_path"),
        "photographer": banner_data.get("photographer", "OdishaExamPrep Official Banner"),
        "is_ai_generated": False
    }
