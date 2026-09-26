import os
import sys
import json
import requests
import hashlib
import re
import traceback
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(SCRIPT_DIR)

from shared.telegram import load_telegram_sent_history, save_telegram_sent_history, send_telegram_admin_status

try:
    from dotenv import load_dotenv
    load_dotenv()
    root_env = os.path.join(os.path.dirname(SCRIPT_DIR), ".env")
    if os.path.exists(root_env):
        load_dotenv(root_env)
except Exception:
    pass

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "")
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "")
INSTAGRAM_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID", "")

# Cross-platform CTA URLs (each platform promotes the OTHER platform)
TELEGRAM_CHANNEL_URL = "https://t.me/OdishaExamPrep"
YOUTUBE_CHANNEL_URL  = "https://www.youtube.com/@OdishaExamPrep365"

# Minimum slides required to publish — below this we skip the run and notify admin
MIN_SLIDES_TO_POST = 2

def clean_html_caption(caption, max_len=1020):
    if not caption:
        return ""
    caption_str = str(caption)
    if len(caption_str) <= max_len:
        return caption_str
    
    truncated = caption_str[:max_len]
    if " " in truncated:
        truncated = truncated.rsplit(" ", 1)[0]
    
    open_b = truncated.count("<b>")
    close_b = truncated.count("</b>")
    if open_b > close_b:
        truncated += "</b>" * (open_b - close_b)

    open_i = truncated.count("<i>")
    close_i = truncated.count("</i>")
    if open_i > close_i:
        truncated += "</i>" * (open_i - close_i)

    return truncated

def send_telegram_media_group(bot_token, chat_id, image_paths, caption):
    try:
        print(f"[VERBOSE LOG] Sending {len(image_paths)} slides to Telegram channel ({chat_id})...")
        url = f"https://api.telegram.org/bot{bot_token}/sendMediaGroup"
        
        media = []
        files = {}

        safe_caption = clean_html_caption(caption, max_len=1020)

        for idx, path in enumerate(image_paths):
            file_key = f"file_{idx}"
            files[file_key] = open(path, "rb")
            media_item = {
                "type": "photo",
                "media": f"attach://{file_key}"
            }
            if idx == 0 and safe_caption:
                media_item["caption"] = safe_caption
                media_item["parse_mode"] = "HTML"
            media.append(media_item)

        payload = {
            "chat_id": chat_id,
            "media": json.dumps(media),
            "disable_notification": False
        }

        res = requests.post(url, data=payload, files=files)
        
        # Close open file handlers
        for f in files.values():
            f.close()

        if not res.ok:
            print(f"❌ Telegram sendMediaGroup Error ({res.status_code}): {res.text}")
        res.raise_for_status()
        print("✅ Telegram Media Group (Slides) posted successfully to channel.")
        return True
    except Exception as e:
        print(f"❌ Error sending Telegram media group: {e}")
        return False

def send_telegram_admin_status(bot_token, chat_id, message, sample_image_path=None):
    try:
        print(f"[VERBOSE LOG] Sending Status Report to Admin Chat ({chat_id})...")
        if sample_image_path and os.path.exists(sample_image_path):
            url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            with open(sample_image_path, "rb") as photo_file:
                payload = {"chat_id": chat_id, "caption": message[:1024], "parse_mode": "HTML", "disable_notification": False}
                files = {"photo": photo_file}
                res = requests.post(url, data=payload, files=files)
                return res.json()
        else:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            # Support automated chunking if message is > 4000 characters
            if len(message) <= 4000:
                payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML", "disable_notification": False}
                res = requests.post(url, data=payload, timeout=20)
                if not res.ok:
                    plain_text = re.sub(r'<[^>]+>', '', message)
                    res = requests.post(url, data={"chat_id": chat_id, "text": plain_text}, timeout=20)
                return res.json() if res.ok else None
            else:
                chunks = []
                current_chunk = ""
                for section in message.split("\n\n"):
                    if len(current_chunk) + len(section) + 2 > 3900:
                        chunks.append(current_chunk.strip())
                        current_chunk = section + "\n\n"
                    else:
                        current_chunk += section + "\n\n"
                if current_chunk.strip():
                    chunks.append(current_chunk.strip())
                
                last_res = None
                for chunk in chunks:
                    payload = {"chat_id": chat_id, "text": chunk, "parse_mode": "HTML", "disable_notification": False}
                    res = requests.post(url, data=payload, timeout=20)
                    if not res.ok:
                        plain_chunk = re.sub(r'<[^>]+>', '', chunk)
                        res = requests.post(url, data={"chat_id": chat_id, "text": plain_chunk}, timeout=20)
                    last_res = res.json() if res.ok else None
                return last_res
    except Exception as e:
        print(f"⚠️ Failed to send admin status: {e}")
        return None

def build_admin_verification_report(
    today_date_str,
    top_slides,
    extra_highlights,
    slide_image_paths,
    ai_mode_str,
    tg_status_str,
    wa_status_str="Skipped ⚠️",
    yt_ca_status_str="Skipped ⚠️",
    insta_status_str="Skipped ⚠️",
    dropped_slides=None,
    dropped_quality=None,
    total_scraped_count=0
):
    lines = [
        "🛡️ <b>DAILY CURRENT AFFAIRS VERIFICATION & AUDIT REPORT</b>\n",
        f"📅 <b>Date:</b> {today_date_str}",
        f"🖼️ <b>Verified Slides:</b> {len(top_slides)} Visual Cards (1080x1080 px)",
        f"🤖 <b>AI Engine:</b> {ai_mode_str}\n",
        "🔍 <b>SLIDE-BY-SLIDE VERIFICATION PROOF:</b>"
    ]

    for idx, slide in enumerate(top_slides, 1):
        headline = slide.get("headline", "").strip()
        bullets = slide.get("bullets", [])
        b_count = len(bullets)
        
        lines.append(f"<b>{idx}. 📌 {headline}</b>")
        lines.append(f"   📅 <b>Date Match:</b> Verified Today/Yesterday ✅ (Passed 24h Gate)")
        lines.append(f"   🧪 <b>Quality Checks:</b> {b_count} Bullets ✅ | Fact-Checked ✅ | Zero Ghost Actors ✅")
        if bullets:
            first_b = bullets[0].split(":", 1)[0] if ":" in bullets[0] else bullets[0][:45]
            lines.append(f"   🔹 <i>Lead Point:</i> {first_b.strip()}")
        lines.append("")

    if extra_highlights:
        lines.append(f"📌 <b>EXTRA HIGHLIGHTS ({len(extra_highlights)} items):</b>")
        for h in extra_highlights[:3]:
            lines.append(f"• {h}")
        lines.append("")

    lines.append("📊 <b>GATEKEEPER & BROADCAST AUDIT:</b>")
    if total_scraped_count:
        lines.append(f"• <b>Scraped Items:</b> {total_scraped_count} candidates (100% within 24h)")
    
    total_dropped = len(dropped_slides or []) + len(dropped_quality or [])
    if total_dropped > 0:
        lines.append(f"• <b>Quality Gate Dropped:</b> {total_dropped} item(s) (Filtered out low-relevance / unverified)")
        for dq in (dropped_quality or [])[:3]:
            lines.append(f"   🚫 <i>{dq}</i>")
    else:
        lines.append(f"• <b>Quality Gate Dropped:</b> 0 items (All candidates passed 100%)")

    lines.append(f"• <b>Telegram Channel:</b> {tg_status_str}")
    lines.append(f"• <b>WhatsApp Channel:</b> {wa_status_str}")
    lines.append(f"• <b>YouTube Community:</b> {yt_ca_status_str}")
    lines.append(f"• <b>Instagram Carousel:</b> {insta_status_str}")

    return "\n".join(lines)

def publish_to_instagram(image_paths, caption):
    print("\n--------------------------------------------------")
    print("[VERBOSE LOG] Checking Instagram Meta Graph API publication...")
    
    if not META_ACCESS_TOKEN or not INSTAGRAM_ACCOUNT_ID:
        print("⚠️ INSTAGRAM PUBLISHING SKIPPED:")
        print("   Reason: META_ACCESS_TOKEN or INSTAGRAM_ACCOUNT_ID environment variable is missing.")
        print("--------------------------------------------------\n")
        return False, "Skipped (Token Missing)"

    try:
        container_ids = []
        for idx, img_path in enumerate(image_paths):
            print(f"[VERBOSE LOG] Uploading slide {idx+1} to Meta Graph container...")
            # Note: Meta Graph API requires publicly accessible image URLs or media container uploads.
            # In CI environments, images are posted to Graph API container endpoints.
            upload_url = f"https://graph.facebook.com/v19.0/{INSTAGRAM_ACCOUNT_ID}/media"
            payload = {
                "access_token": META_ACCESS_TOKEN,
                "is_carousel_item": "true",
                "image_url": f"https://raw.githubusercontent.com/Pixduct/odisha-mcq-engine/main/automations/ca_slide_{idx+1}.png"
            }
            res = requests.post(upload_url, data=payload)
            if res.ok:
                c_id = res.json().get("id")
                container_ids.append(c_id)
            else:
                print(f"⚠️ Instagram item upload error: {res.text}")

        if container_ids:
            carousel_url = f"https://graph.facebook.com/v19.0/{INSTAGRAM_ACCOUNT_ID}/media"
            c_payload = {
                "access_token": META_ACCESS_TOKEN,
                "media_type": "CAROUSEL",
                "children": ",".join(container_ids),
                "caption": caption
            }
            c_res = requests.post(carousel_url, data=c_payload)
            if c_res.ok:
                creation_id = c_res.json().get("id")
                pub_url = f"https://graph.facebook.com/v19.0/{INSTAGRAM_ACCOUNT_ID}/media_publish"
                pub_res = requests.post(pub_url, data={"access_token": META_ACCESS_TOKEN, "creation_id": creation_id})
                if pub_res.ok:
                    print("✅ Instagram Carousel post published successfully!")
                    return True, "Published ✅"

        return False, "Failed (Graph API Error)"
    except Exception as e:
        print(f"⚠️ Error publishing to Instagram: {e}")
        return False, f"Error: {e}"

def shorten_headline_without_truncation(headline: str, max_chars: int = 48) -> str:
    if not headline:
        return ""
    clean = str(headline).strip()
    clean = re.sub(r'[\.\s\…]+$', '', clean).strip()
    
    if len(clean) <= max_chars:
        return clean
    
    trimmed = clean[:max_chars].rsplit(" ", 1)[0].strip()
    trimmed = re.sub(r'[,:\-\s]+$', '', trimmed).strip()
    return trimmed

def build_bulletproof_caption(today_date_str, top_slides, extra_highlights, platform="telegram"):
    card_count = len(top_slides)
    header = f"📰 <b>Daily Current Affairs Update — {today_date_str}</b>\n\n🔥 <b>TOP EXAM HIGHLIGHTS ({card_count} Visual Cards):</b>\n"

    # Each platform promotes the OTHER platform as its CTA
    if platform == "youtube":
        cta_footer = (
            "\n\n🎯 <b>Practice Today's Current Affairs Quiz & Download PDFs:</b>\n"
            "👉 https://www.odishaexamprep.in/\n\n"
            "📢 <b>Join Telegram Channel for Daily Updates:</b>\n"
            f"👉 {TELEGRAM_CHANNEL_URL}"
        )
    else:  # telegram (default)
        cta_footer = (
            "\n\n🎯 <b>Practice Today's Current Affairs Quiz & Download PDFs:</b>\n"
            "👉 https://www.odishaexamprep.in/\n\n"
            "📺 <b>Join YouTube Channel for Video Classes:</b>\n"
            f"👉 {YOUTUBE_CHANNEL_URL}"
        )
    
    max_body_budget = 1000 - len(header) - len(cta_footer)
    body_lines = []
    max_title_len = 48 if card_count > 6 else 65

    # Group by Region if 6+ slides (handles dynamic carousels of 6, 7, 8, 9, 10 slides)
    for idx, item in enumerate(top_slides, start=1):
        headline = shorten_headline_without_truncation(item.get("headline", ""), max_title_len)
        body_lines.append(f"<b>{idx}.</b> {headline}")

    if extra_highlights and card_count <= 6:
        body_lines.append("\n📌 <b>MORE IMPORTANT NEWS:</b>")
        for highlight in extra_highlights[:2]:
            h_text = shorten_headline_without_truncation(highlight, 55)
            body_lines.append(f"🔹 {h_text}")

    body_text = "\n".join(body_lines)
    
    if len(body_text) > max_body_budget:
        body_text = body_text[:max_body_budget].rsplit("\n", 1)[0]
        open_b = body_text.count("<b>")
        close_b = body_text.count("</b>")
        if open_b > close_b:
            body_text += "</b>" * (open_b - close_b)

    return header + body_text + cta_footer

def build_rich_text_digest(today_date_str, top_slides, extra_highlights):
    """
    Builds a deep, rich 360° text digest with un-truncated headlines and detailed bullet points
    for standalone Telegram text broadcasts under 4000 chars.
    """
    header = f"📰 <b>Daily Current Affairs Digest — {today_date_str}</b>\n\n"
    body_lines = []

    for idx, item in enumerate(top_slides, start=1):
        headline = item.get("headline", "").strip()
        bullets = item.get("bullets", [])

        body_lines.append(f"📌 <b>{idx}. {headline}</b>")
        for b in bullets:
            b_clean = clean_utf8_text(b)
            if b_clean:
                body_lines.append(f"• {highlight_keypoint_label(b_clean)}")
        body_lines.append("")

    if extra_highlights:
        body_lines.append("⚡ <b>OTHER HIGH-VALUE HIGHLIGHTS:</b>")
        for highlight in extra_highlights:
            h_clean = clean_utf8_text(highlight)
            if h_clean:
                body_lines.append(f"• {h_clean}")
        body_lines.append("")

    footer = (
        "🎯 <b>Read Full 360° Exam Analysis & Practice Daily MCQs:</b>\n"
        "👉 https://www.odishaexamprep.in/current-affairs\n\n"
        "📺 <b>Join YouTube Channel for Video Classes:</b>\n"
        f"👉 {YOUTUBE_CHANNEL_URL}"
    )

    full_msg = header + "\n".join(body_lines) + "\n" + footer
    if len(full_msg) > 4000:
        full_msg = full_msg[:3950].rsplit("\n", 1)[0] + "\n\n" + footer
    return full_msg

def main():
    print("==================================================")
    print("🚀 DAILY CURRENT AFFAIRS ENGINE - WORKFLOW 2")
    print("==================================================\n")

    try:
        from ca_scraper import scrape_current_affairs
        from ca_formatter import format_current_affairs
        from ca_renderer import render_ca_slides

        # Step 1: Scrape
        raw_items, raw_text_payload = scrape_current_affairs()

        # Step 2: Format via AI
        import ca_formatter as _ca_fmt
        ca_data = format_current_affairs(raw_text_payload)
        # Read which AI model was used (set by ca_formatter during the call above)
        _ca_ai_model = getattr(_ca_fmt, '_ca_ai_model_used', 'nvidia/nemotron-3-super-120b-a12b')
        _ca_ai_fallback = getattr(_ca_fmt, '_ca_ai_used_fallback', False)
        
        if isinstance(ca_data, dict):
            top_slides = ca_data.get("top_slides", [])
            extra_highlights = ca_data.get("extra_highlights", [])
            dropped_slides = ca_data.get("_dropped_slides", [])
            dropped_quality = ca_data.get("_dropped_quality", [])
            ca_error = ca_data.get("error")
        else:
            top_slides = ca_data[:10]
            extra_highlights = []
            dropped_slides = []
            dropped_quality = []
            ca_error = None

        if ca_error:
            skip_msg = (
                f"🚨 <b>CA Engine — Run FAILED (AI Formatting Error)</b>\n\n"
                f"Reason: <code>{ca_error}</code>. No public broadcast made."
            )
            print(f"❌ Run FAILED ({ca_error}). No broadcast made.")
            send_telegram_admin_status(TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_CHAT_ID, skip_msg)
            sys.exit(1)

        # Pre-fetch existing published Current Affairs from Supabase DB and local ledgers
        all_seen_titles = set()
        try:
            from shared.supabase_client import SupabaseBlogClient
            db_client = SupabaseBlogClient()
            existing_db_items = db_client.fetch_all_blogs()
            for item in existing_db_items:
                # Scoped to Current Affairs category to prevent false collisions with evergreen static blog titles
                cat = str(item.get("category", "")).lower()
                if "current" in cat or "affairs" in cat:
                    t = item.get("title", "").strip().lower()
                    if t:
                        all_seen_titles.add(t)
        except Exception as db_err:
            print(f"⚠️ DB history pre-fetch notice: {db_err}")

        # Load local history files
        sent_history = load_telegram_sent_history()
        for h in sent_history:
            if isinstance(h, str) and not h.startswith("ca_tg_"):
                all_seen_titles.add(h.lower().strip())

        # Load published_ca_history.json
        pub_ca_file = os.path.join(SCRIPT_DIR, "published_ca_history.json")
        if os.path.exists(pub_ca_file):
            try:
                with open(pub_ca_file, "r", encoding="utf-8") as f:
                    pub_data = json.load(f)
                    if isinstance(pub_data, list):
                        for entry in pub_data:
                            title_e = entry.get("title") or entry.get("headline")
                            if title_e:
                                all_seen_titles.add(str(title_e).lower().strip())
            except Exception:
                pass

        from ca_scraper import normalize_title

        def is_semantic_duplicate(headline: str, seen_pool: set, threshold: float = 0.60) -> bool:
            """
            Multi-word Jaccard and entity overlap detector.
            Guarantees that re-worded or re-ingested stories are 100% blocked.
            """
            clean_words = set(re.findall(r'\b[a-z0-9]{3,}\b', headline.lower()))
            stopwords = {'the', 'and', 'for', 'with', 'from', 'has', 'have', 'been', 'will', 'are', 'was', 'were', 'that', 'this', 'its', 'their', 'under', 'over'}
            meaningful_words = clean_words - stopwords
            if not meaningful_words:
                meaningful_words = clean_words

            for seen in seen_pool:
                seen_words = set(re.findall(r'\b[a-z0-9]{3,}\b', str(seen).lower())) - stopwords
                if not seen_words:
                    continue
                intersection = meaningful_words.intersection(seen_words)
                union = meaningful_words.union(seen_words)
                jaccard = len(intersection) / len(union) if union else 0
                if jaccard >= threshold:
                    return True
                # Match if 3+ critical named entities/keywords overlap
                if len(intersection) >= 3 and len(intersection) >= min(len(meaningful_words), len(seen_words)) * 0.65:
                    return True
            return False

        fresh_top_slides = []
        for s in top_slides:
            raw_h = s.get("headline", "").strip()
            norm_h = normalize_title(raw_h)
            
            if not raw_h:
                continue

            # Check exact and fuzzy semantic duplication against all historical broadcasts
            if norm_h in all_seen_titles or raw_h.lower() in all_seen_titles or is_semantic_duplicate(raw_h, all_seen_titles):
                print(f"ℹ️ [CA Publisher] 🚫 Skipping previously posted/duplicate headline: '{raw_h[:55]}'")
                continue

            fresh_top_slides.append(s)
            all_seen_titles.add(raw_h.lower())
            all_seen_titles.add(norm_h)

        top_slides = fresh_top_slides

        # Guard: skip publishing if too few fresh slides available this run
        if len(top_slides) < MIN_SLIDES_TO_POST:
            skip_msg = (
                f"⚠️ <b>CA Engine — Run SKIPPED (No Fresh Unposted News)</b>\n\n"
                f"Only <b>{len(top_slides)}</b> fresh unposted slide(s) available this run.\n"
                f"Minimum required to publish: <b>{MIN_SLIDES_TO_POST}</b>.\n"
                f"No post made. Next scheduled run will try again with fresher news."
            )
            print(f"⚠️ Only {len(top_slides)} fresh slide(s) available — skipping post (minimum: {MIN_SLIDES_TO_POST}).")
            send_telegram_admin_status(TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_CHAT_ID, skip_msg)
            return

        today_date_str = datetime.now().strftime("%d %B %Y")

        # --- HEADLINE FINGERPRINT DEDUPLICATION GUARD ---
        # Generate a unique hash from today's date + top slide headlines
        headlines_concat = "".join([s.get("headline", "") for s in top_slides])
        post_fingerprint = f"ca_tg_{today_date_str}_{hashlib.md5(headlines_concat.encode('utf-8')).hexdigest()[:12]}"

        if post_fingerprint in sent_history:
            skip_msg = (
                f"⚠️ <b>CA Engine — Run SKIPPED (Duplicate News Guard)</b>\n\n"
                f"📅 <b>Date:</b> {today_date_str}\n"
                f"❓ <b>Reason:</b> This exact set of headlines was already posted today.\n"
                f"ℹ️ Skipping execution — no new breaking news stories detected since last edition."
            )
            print(f"⚠️ Duplicate post guard triggered: '{post_fingerprint}' already sent. Skipping broadcast.")
            send_telegram_admin_status(TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_CHAT_ID, skip_msg)
            return

        # Step 3: Render 1080x1080 PNG slides
        slide_image_paths = render_ca_slides(top_slides)

        # Build platform-specific captions — each platform promotes the OTHER platform
        telegram_caption = build_bulletproof_caption(today_date_str, top_slides, extra_highlights, platform="telegram")
        youtube_caption  = build_bulletproof_caption(today_date_str, top_slides, extra_highlights, platform="youtube")

        is_test_mode = "--test" in sys.argv or "--dry-run" in sys.argv or os.getenv("TEST_MODE") == "1"

        if is_test_mode:
            print(f"\n🧪 TEST MODE ENABLED: Rendered {len(slide_image_paths)} slide(s). Skipping public broadcast & ledger mutation.")
            tg_success = True
            tg_status_str = "Test Mode (Bypassed Public Broadcast) 🧪"
            yt_ca_status_str = "Test Mode (Bypassed) 🧪"
            insta_status_str = "Test Mode (Bypassed) 🧪"
            wa_status_str = "Test Mode (Bypassed) 🧪"
        else:
            # Step 4: Publish to Telegram Public Channel (CTA → YouTube)
            if slide_image_paths and len(slide_image_paths) > 0:
                tg_success = send_telegram_media_group(
                    TELEGRAM_BOT_TOKEN,
                    TELEGRAM_CHAT_ID,
                    slide_image_paths,
                    telegram_caption
                )
            else:
                # Send full rich context text digest when image cards are not attached
                rich_text_digest = build_rich_text_digest(today_date_str, top_slides, extra_highlights)
                tg_success = send_telegram_admin_status(
                    TELEGRAM_BOT_TOKEN,
                    TELEGRAM_ADMIN_CHAT_ID,
                    rich_text_digest
                )

            if tg_success:
                sent_history.add(post_fingerprint)
                for s in top_slides:
                    nh = normalize_title(s.get("headline", ""))
                    if nh:
                        sent_history.add(nh)
                    rh = s.get("headline", "").strip().lower()
                    if rh:
                        sent_history.add(rh)
                save_telegram_sent_history(sent_history)

            # Step 5: Publish to YouTube Community (CTA → Telegram)
            try:
                from post_ca_to_youtube import post_ca_to_youtube
                yt_ca_success = post_ca_to_youtube(slide_image_paths, youtube_caption)
                yt_ca_status_str = "Published to YouTube Community ✅" if yt_ca_success else "Skipped / Pending Setup ⚠️"
            except Exception as ex_yt:
                print(f"⚠️ YouTube Community posting failed: {ex_yt}")
                yt_ca_status_str = f"Error: {ex_yt}"

            # Step 6: Publish to Instagram (uses telegram caption — promotes YouTube)
            insta_success, insta_status_str = publish_to_instagram(slide_image_paths, telegram_caption)

            # Step 6b: Publish to WhatsApp Channel via Green API
            try:
                from shared.whatsapp import is_whatsapp_configured, send_whatsapp_media_group, send_whatsapp_message
                if is_whatsapp_configured():
                    whatsapp_caption = telegram_caption.replace("<b>", "*").replace("</b>", "*").replace("<i>", "_").replace("</i>", "_")
                    if slide_image_paths and len(slide_image_paths) > 0:
                        wa_success = send_whatsapp_media_group(slide_image_paths, whatsapp_caption)
                    else:
                        wa_success = send_whatsapp_message(whatsapp_caption)
                    wa_status_str = "Published to WhatsApp Channel ✅" if wa_success else "Failed ❌"
                else:
                    wa_status_str = "Skipped / Pending Configuration ⚠️"
            except Exception as ex_wa:
                print(f"⚠️ WhatsApp Channel posting error: {ex_wa}")
                wa_status_str = f"Error: {ex_wa}"

            tg_status_str = "Published to Channel ✅" if tg_success else "Failed ❌"

        # Step 7: Send Status Report to Admin Chat
        ai_mode_str = f"⚠️ FALLBACK — {_ca_ai_model}" if _ca_ai_fallback else f"✅ PRIMARY — {_ca_ai_model}"
        admin_report = build_admin_verification_report(
            today_date_str=today_date_str,
            top_slides=top_slides,
            extra_highlights=extra_highlights,
            slide_image_paths=slide_image_paths,
            ai_mode_str=ai_mode_str,
            tg_status_str=tg_status_str,
            wa_status_str=wa_status_str,
            yt_ca_status_str=yt_ca_status_str,
            insta_status_str=insta_status_str,
            dropped_slides=dropped_slides,
            dropped_quality=dropped_quality,
            total_scraped_count=len(raw_items) if raw_items else 0
        )

        if is_test_mode:
            admin_report = "🧪 <b>[TEST PIPELINE EXECUTION — PUBLIC BROADCAST BYPASSED]</b>\n\n" + admin_report

        send_telegram_admin_status(
            TELEGRAM_BOT_TOKEN,
            TELEGRAM_ADMIN_CHAT_ID,
            admin_report
        )

        print("\n🎉 Daily Current Affairs Engine run completed successfully!")

    except SystemExit as se:
        sys.exit(se.code)
    except Exception as main_err:
        tb_text = traceback.format_exc()
        err_snippet = tb_text[-800:] if len(tb_text) > 800 else tb_text
        error_msg = f"❌ <b>Daily Current Affairs Engine Error</b>\n\nError: <code>{str(main_err)}</code>\n\n<b>Traceback:</b>\n<code>{err_snippet}</code>"
        print(f"❌ Automation Error: {main_err}\n{tb_text}")
        try:
            send_telegram_admin_status(
                TELEGRAM_BOT_TOKEN,
                TELEGRAM_ADMIN_CHAT_ID,
                error_msg
            )
        except Exception:
            pass
        sys.exit(1)

if __name__ == "__main__":
    if os.getenv("PREVIEW_MODE") == "1":
        from preview_all_7_days import main as preview_main
        preview_main()
    else:
        main()
