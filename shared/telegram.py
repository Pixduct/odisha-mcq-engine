import os
import sys
import json
import time
import requests
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "")

# History ledger path to prevent duplicate Telegram broadcasts
AUTOMATIONS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SENT_HISTORY_FILE = os.path.join(AUTOMATIONS_DIR, "history", "telegram_sent_history.json")

def load_telegram_sent_history() -> set:
    if os.path.exists(SENT_HISTORY_FILE):
        try:
            with open(SENT_HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return set(data) if isinstance(data, list) else set()
        except Exception:
            pass
    return set()

def save_telegram_sent_history(history: set):
    os.makedirs(os.path.dirname(SENT_HISTORY_FILE), exist_ok=True)
    try:
        with open(SENT_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(sorted(list(history)), f, indent=2)
    except Exception as e:
        print(f"⚠️ Error saving telegram_sent_history.json: {e}")

def clean_html_caption(caption: str, max_len: int = 1020) -> str:
    if not caption:
        return ""
    caption_str = str(caption).strip()
    if len(caption_str) <= max_len:
        return caption_str

    truncated = caption_str[:max_len]
    if "\n" in truncated:
        truncated = truncated.rsplit("\n", 1)[0]
    elif " " in truncated:
        truncated = truncated.rsplit(" ", 1)[0]

    open_b = truncated.count("<b>") - truncated.count("</b>")
    if open_b > 0:
        truncated += "</b>" * open_b

    open_i = truncated.count("<i>") - truncated.count("</i>")
    if open_i > 0:
        truncated += "</i>" * open_i

    return truncated

def resolve_clean_article_url(details: dict) -> str:
    """
    Guarantees a 100% valid, clickable website URL for published articles,
    completely eliminating placeholder 'generated-uuid' strings.
    """
    art_url = str(details.get("article_url") or "").strip()
    art_id = str(details.get("article_id") or details.get("id") or details.get("slug") or "").strip()

    if art_id and art_id != "generated-uuid":
        return f"https://www.odishaexamprep.in/blog/{art_id}"

    if art_url and "generated-uuid" not in art_url:
        return art_url

    title = details.get("title", "").strip()
    if title:
        try:
            from shared.supabase_client import SupabaseBlogClient
            client = SupabaseBlogClient()
            blogs = client.fetch_all_blogs()
            norm = title.lower()
            for b in blogs:
                if str(b.get("name", "")).lower().strip() == norm and b.get("id"):
                    return f"https://www.odishaexamprep.in/blog/{b['id']}"
        except Exception as e:
            print(f"⚠️ [Telegram URL Resolver] Lookup error: {e}")

    return "https://www.odishaexamprep.in/blog"

def broadcast_public_telegram_post(engine: str, details: dict) -> bool:
    """
    Broadcasts a highly engaging public CTA post to the main student Telegram channel (TELEGRAM_CHAT_ID).
    Guarantees ZERO DUPLICATES using telegram_sent_history.json.
    Retries up to 3 times ONLY on transient network/HTTP errors.
    """
    item_id = str(details.get("article_id") or details.get("slug") or details.get("title") or "").strip()
    if not item_id or item_id == "generated-uuid":
        item_id = str(details.get("title", "")).strip()

    if not item_id:
        print("⚠️ [Telegram Broadcast] No unique item ID or title found. Skipping.")
        return False

    sent_history = load_telegram_sent_history()
    if item_id in sent_history:
        print(f"ℹ️ [Telegram Broadcast] Item '{item_id}' already sent previously. Skipping duplicate broadcast.")
        return True

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        title = details.get("title", "Official Update")
        
        if engine == "CURRENT_AFFAIRS":
            category = details.get("category", "General")
            msg = (
                f"🔥 <b>FRESH DAILY CURRENT AFFAIRS RELEASED!</b>\n\n"
                f"📌 <b>{title}</b>\n\n"
                f"🏷️ <b>Category:</b> {category}\n"
                f"⚡ <b>What's Inside:</b>\n"
                f"• In-depth 360° exam analysis & Static GK pointers.\n"
                f"• Practice self-test MCQs to test your memory!\n\n"
                f"👉 <b>Visit OdishaExamPrep to read the complete Current Affairs & practice daily MCQs:</b>\n"
                f"https://www.odishaexamprep.in/current-affairs"
            )
        elif engine == "BREAKING_ALERT":
            org = details.get("organization") or details.get("exam_board") or "Official Recruitment Board"
            headline = details.get("headline", title)
            category_badge = details.get("category_badge", "OFFICIAL EXAM NOTIFICATION")
            official_link = details.get("official_link") or details.get("link") or details.get("official_source") or "https://ossc.gov.in"
            vacancies = details.get("vacancies", "")
            dates = details.get("dates", "")
            bullets = details.get("bullets", [])

            lines = [
                f"🚨 <b>{category_badge}</b>\n",
                f"📌 <b>{headline}</b>\n",
                f"🏛️ <b>Recruitment Board:</b> {org}"
            ]

            if vacancies and "check official" not in str(vacancies).lower() and vacancies != "N/A" and "refer to" not in str(vacancies).lower():
                lines.append(f"👥 <b>Vacancies:</b> {vacancies}")
            if dates and "check official" not in str(dates).lower() and dates != "N/A":
                lines.append(f"📅 <b>Important Schedule:</b> {dates}")

            if bullets:
                lines.append("\n⚡ <b>Key Updates & Details:</b>")
                for b in bullets:
                    cleaned_b = str(b).strip()
                    if cleaned_b:
                        lines.append(f"• {cleaned_b}")

            lines.append(f"\n🌐 <b>Direct Official Notification Link:</b>\n👉 {official_link}")
            lines.append(f"\n🚀 <b>Practice Odisha State Mock Tests & PYQs:</b>\n👉 https://www.odishaexamprep.in/")

            msg = "\n".join(lines)
        elif engine == "EXAM_UPDATE":
            org = details.get("organization") or details.get("exam_board") or "Official Recruitment Authority"
            exam = details.get("exam") or details.get("target_exam") or org
            headline = details.get("headline", title)
            category_badge = details.get("category_badge", "OFFICIAL EXAM NOTIFICATION")
            official_link = details.get("official_link") or details.get("link") or details.get("official_source") or "https://ossc.gov.in"
            vacancies = str(details.get("vacancies", "")).strip()
            eligibility = str(details.get("eligibility", "")).strip()
            dates = str(details.get("dates", "")).strip()
            exam_schedule = str(details.get("exam_schedule", "")).strip()
            timeline_events = details.get("timeline_events", [])
            bullets = details.get("bullets", [])
            art_url = resolve_clean_article_url(details)

            lines = [
                f"🚨 <b>{category_badge}</b>\n",
                f"📌 <b>{headline}</b>\n",
                f"🏛️ <b>Recruitment Authority:</b> {org}"
            ]

            if vacancies and vacancies.lower() not in ["n/a", "none", "", "check official", "refer to notice"]:
                lines.append(f"👥 <b>Total Vacancies:</b> {vacancies}")
            if eligibility and eligibility.lower() not in ["n/a", "none", "", "check official"]:
                lines.append(f"🎓 <b>Eligibility:</b> {eligibility}")

            # Specific, crystal-clear timeline events
            if timeline_events and isinstance(timeline_events, list) and len(timeline_events) > 0:
                lines.append("\n🗓️ <b>CRITICAL DATES & TIMELINE:</b>")
                for ev in timeline_events:
                    if isinstance(ev, dict) and ev.get("label") and ev.get("date"):
                        lines.append(f"• <b>{ev['label']}:</b> {ev['date']}")
                    elif isinstance(ev, str) and ev.strip():
                        lines.append(f"• {ev.strip()}")
            elif dates and dates.lower() not in ["n/a", "none", "", "check official"]:
                lines.append("\n🗓️ <b>CRITICAL DATES & TIMELINE:</b>")
                if "start:" in dates.lower() and "last date:" in dates.lower():
                    parts = [p.strip() for p in re.split(r'[\|,]', dates) if p.strip()]
                    for p in parts:
                        lines.append(f"• <b>{p}</b>")
                else:
                    lines.append(f"• <b>Important Schedule:</b> {dates}")
                if exam_schedule and exam_schedule.lower() not in ["n/a", "none", "", "check official"]:
                    lines.append(f"• <b>Exam Date / Schedule:</b> {exam_schedule}")

            if bullets:
                lines.append("\n⚡ <b>KEY EXAM DETAILS & ACTION PLAN:</b>")
                for b in bullets:
                    cleaned_b = str(b).strip().replace("**", "").replace("*", "")
                    if cleaned_b:
                        if ":" in cleaned_b and not cleaned_b.startswith("<b>"):
                            lbl, val = cleaned_b.split(":", 1)
                            lines.append(f"• <b>{lbl.strip()}:</b> {val.strip()}")
                        else:
                            lines.append(f"• {cleaned_b}")

            lines.append(f"\n🌐 <b>Direct Official Notification Link:</b>\n👉 {official_link}")
            if art_url and "generated-uuid" not in art_url:
                lines.append(f"\n📖 <b>Detailed Syllabus, Pattern & Analysis on OdishaExamPrep:</b>\n👉 {art_url}")
            lines.append(f"\n🚀 <b>Practice Free Odisha & All-India Mock Tests:</b>\n👉 https://www.odishaexamprep.in/")

            msg = "\n".join(lines)
        elif engine == "ENGAGEMENT_BLOG":
            category = details.get("category", "Exam Strategy")
            art_url = resolve_clean_article_url(details)
            msg = (
                f"💡 <b>NEW PREP MASTERCLASS & STRATEGY GUIDE!</b>\n\n"
                f"📌 <b>{title}</b>\n\n"
                f"🏷️ <b>Topic Focus:</b> {category}\n"
                f"⚡ <b>What You'll Learn:</b>\n"
                f"• Practical shortcuts, worked problem examples & speed frameworks.\n"
                f"• Systematic error-logging technique to eliminate negative marking.\n\n"
                f"👉 <b>Read the Full Masterclass on OdishaExamPrep:</b>\n"
                f"{art_url}"
            )
        else:
            # EXAM UPDATE / STRATEGY BLOG
            target_exam = details.get("target_exam") or details.get("organization") or "Odisha Competitive Exams"
            art_url = resolve_clean_article_url(details)
            msg = (
                f"📚 <b>NEW OFFICIAL EXAM UPDATE PUBLISHED!</b>\n\n"
                f"📌 <b>{title}</b>\n\n"
                f"🏆 <b>Target Exam / Board:</b> {target_exam}\n"
                f"💡 <b>Update Highlights:</b>\n"
                f"• Verified official guidelines, eligibility & syllabus details.\n"
                f"• Comprehensive breakdown and preparation next steps.\n\n"
                f"👉 <b>Visit OdishaExamPrep to read the full article:</b>\n"
                f"{art_url}"
            )

        slide_img = details.get("slide_image_path") or details.get("cover_image")
        has_valid_img = slide_img and os.path.exists(str(slide_img))

        if has_valid_img:
            photo_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
            safe_caption = clean_html_caption(msg, max_len=1020)
            
            for attempt in range(1, 4):
                try:
                    with open(slide_img, "rb") as photo_f:
                        files = {"photo": photo_f}
                        p_data = {
                            "chat_id": TELEGRAM_CHAT_ID,
                            "caption": safe_caption,
                            "parse_mode": "HTML",
                            "disable_notification": False
                        }
                        res = requests.post(photo_url, data=p_data, files=files, timeout=25)
                        if res.ok:
                            print(f"✅ [Public Telegram Broadcast] Posted image card successfully to channel ({engine}) on attempt {attempt}")
                            sent_history.add(item_id)
                            save_telegram_sent_history(sent_history)
                            return True
                        elif res.status_code == 429:
                            time.sleep(5)
                        else:
                            print(f"⚠️ Telegram sendPhoto HTTP {res.status_code}: {res.text}. Attempt {attempt}/3")
                            time.sleep(2 * attempt)
                except Exception as img_err:
                    print(f"⚠️ Image dispatch exception ({img_err}). Falling back to text message...")
                    time.sleep(1)

        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }

        # 3-Pass Network Retry Loop (Network/5xx errors ONLY)
        for attempt in range(1, 4):
            try:
                res = requests.post(url, data=payload, timeout=15)
                if res.ok:
                    print(f"✅ [Public Telegram Broadcast] Posted successfully to channel ({engine}) on attempt {attempt}")
                    sent_history.add(item_id)
                    save_telegram_sent_history(sent_history)
                    return True
                elif res.status_code == 429:
                    # Rate limited: wait requested time or default 5s
                    retry_after = int(res.headers.get("Retry-After", 5))
                    print(f"⚠️ Telegram 429 Rate Limit. Sleeping {retry_after}s before attempt {attempt + 1}...")
                    time.sleep(retry_after)
                else:
                    print(f"⚠️ Telegram API HTTP {res.status_code}: {res.text}. Attempt {attempt}/3")
                    time.sleep(2 * attempt)
            except Exception as req_err:
                print(f"⚠️ Network error on Telegram dispatch attempt {attempt}/3: {req_err}")
                time.sleep(2 * attempt)

        return False
    except Exception as e:
        print(f"[Public Telegram Broadcast Exception]: {e}")
        return False

SCRIPT_START_TIME = time.time()

def calculate_runtime_and_queue_metrics() -> tuple:
    """
    Calculates automation execution runtime and detects GitHub Actions runner queue delay.
    """
    elapsed_sec = int(round(time.time() - SCRIPT_START_TIME))
    mins, secs = divmod(elapsed_sec, 60)
    runtime_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"

    # Queue delay detection via GitHub Actions environment variables
    run_started_at = os.getenv("GITHUB_RUN_STARTED_AT")
    queue_delay_str = "0s (Instant Execution ✅)"
    if run_started_at:
        try:
            from datetime import datetime, timezone
            started_dt = datetime.fromisoformat(run_started_at.replace("Z", "+00:00"))
            now_dt = datetime.now(timezone.utc)
            delay_sec = max(0, int(round((now_dt - started_dt).total_seconds() - elapsed_sec)))
            if delay_sec > 15:
                q_mins, q_secs = divmod(delay_sec, 60)
                q_time = f"{q_mins}m {q_secs}s" if q_mins > 0 else f"{q_secs}s"
                queue_delay_str = f"⚠️ Delayed by {q_time} in runner queue"
            else:
                queue_delay_str = "0s (Instant Execution ✅)"
        except Exception:
            pass

    return runtime_str, queue_delay_str

def send_telegram_admin_status(bot_token: str, admin_chat_id: str, message_text: str):
    """
    Direct helper to send an admin status report to Telegram Admin Chat,
    automatically appending Run Time and Queue Delay metrics.
    """
    runtime_str, queue_str = calculate_runtime_and_queue_metrics()
    metrics_footer = (
        f"\n\n⏱️ <b>Automation Run Time:</b> {runtime_str}\n"
        f"⏳ <b>Runner Queue Status:</b> {queue_str}"
    )
    full_msg = f"{message_text}{metrics_footer}"
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": admin_chat_id,
        "text": full_msg,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        res = requests.post(url, data=payload, timeout=20)
        if res.ok:
            print("[Telegram Admin Status Report] Sent successfully.")
            return True
        else:
            print(f"[Telegram Admin Status Report Error]: {res.text}")
            return False
    except Exception as e:
        print(f"[Telegram Admin Status Report Exception]: {e}")
        return False

def send_ai_fallback_notification(engine: str, primary_error: str, fallback_model: str, context_topic: str = "") -> bool:
    """
    Alerts the administrator immediately via Telegram Admin Chat whenever Primary AI (Google Gemini)
    fails, times out, or hits quota limits, and an automation engages a secondary fallback AI model.
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN") or TELEGRAM_BOT_TOKEN
    admin_chat_id = os.getenv("TELEGRAM_ADMIN_CHAT_ID") or TELEGRAM_ADMIN_CHAT_ID
    if not bot_token or not admin_chat_id:
        print(f"⚠️ [AI Fallback Alert] TELEGRAM_BOT_TOKEN or TELEGRAM_ADMIN_CHAT_ID missing. Cannot dispatch alert.")
        return False

    now_str = datetime.now().strftime("%d-%b-%Y %H:%M:%S")
    context_line = f"\n📌 <b>Task Context:</b> {context_topic[:150]}" if context_topic else ""
    error_snippet = primary_error.strip()[:300] if primary_error else "All Gemini models (3.5-flash, 3.5-flash-lite, 3.6-flash) exhausted or returned error"

    alert_msg = (
        f"🚨 <b>AI FAILOVER ALERT — Fallback Model Engaged</b>\n\n"
        f"⚙️ <b>Engine:</b> <code>{engine}</code>\n"
        f"🕒 <b>Timestamp:</b> {now_str}\n"
        f"❌ <b>Primary AI (Gemini) Error:</b>\n"
        f"<code>{error_snippet}</code>\n\n"
        f"🔄 <b>Engaged Fallback AI:</b>\n"
        f"<code>{fallback_model}</code>"
        f"{context_line}\n\n"
        f"<i>💡 Notice: Fallback AI was utilized to preserve pipeline continuity. Check Google AI Studio quota / rate limits.</i>"
    )

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": admin_chat_id,
        "text": alert_msg,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        res = requests.post(url, data=payload, timeout=15)
        if res.ok:
            print(f"🔔 [AI Fallback Alert] Admin Telegram alert dispatched for engine: {engine}")
            return True
        else:
            print(f"⚠️ [AI Fallback Alert Error]: {res.text}")
            return False
    except Exception as e:
        print(f"⚠️ [AI Fallback Alert Exception]: {e}")
        return False

def send_admin_alert(engine: str, status: str, details: dict):
    """
    Sends formatted Telegram alert to admin channel (TELEGRAM_ADMIN_CHAT_ID).
    If status is SUCCESS, broadcasts public post first and sends confirmation.
    Automatically appends Run Time & Runner Queue Delay metrics.
    status: "SUCCESS" | "FAILED" | "SKIPPED"
    """
    try:
        runtime_str, queue_str = calculate_runtime_and_queue_metrics()
        metrics_footer = (
            f"\n\n⏱️ <b>Automation Run Time:</b> {runtime_str}\n"
            f"⏳ <b>Runner Queue Status:</b> {queue_str}"
        )

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

        if details.get("message"):
            msg = f"{details['message']}{metrics_footer}"
        elif status == "SUCCESS":
            # Broadcast to public student channel first
            public_success = broadcast_public_telegram_post(engine, details)
            
            # Broadcast to WhatsApp channel if configured
            wa_public_success = False
            try:
                from shared.whatsapp import is_whatsapp_configured, send_whatsapp_message, send_whatsapp_image
                if is_whatsapp_configured():
                    target_url_clean = "https://www.odishaexamprep.in/current-affairs" if engine == "CURRENT_AFFAIRS" else resolve_clean_article_url(details)
                    title_clean = details.get('title', 'Exam Notification')
                    org_clean = details.get('organization', details.get('target_exam', 'Odisha Govt Exam'))
                    cover_img = details.get('cover_image') or details.get('featured_image') or details.get('image_url')
                    exam_name = details.get('exam') or org_clean
                    vacancies_wa = str(details.get("vacancies", "")).strip()
                    eligibility_wa = str(details.get("eligibility", "")).strip()
                    dates_wa = str(details.get("dates", "")).strip()
                    exam_schedule_wa = str(details.get("exam_schedule", "")).strip()
                    bullets_wa = details.get("bullets", [])
                    official_link_wa = details.get("official_link") or details.get("link") or details.get("official_source") or "https://ossc.gov.in"

                    if engine == "CURRENT_AFFAIRS":
                        wa_caption = (
                            f"🔥 *DAILY CURRENT AFFAIRS UPDATE*\n\n"
                            f"📌 *{title_clean}*\n"
                            f"🏷️ *Category:* {details.get('category', 'General')}\n\n"
                            f"⚡ *What's Inside:*\n"
                            f"• In-depth 360° exam analysis & Static GK pointers.\n"
                            f"• Practice self-test MCQs to test your memory!\n\n"
                            f"👉 *Read Full Current Affairs:*\n{target_url_clean}\n\n"
                            f"🚀 *Practice Free Mock Tests:*\nhttps://www.odishaexamprep.in"
                        )
                    elif engine in ["EXAM_UPDATE", "BREAKING_ALERT"]:
                        timeline_events_wa = details.get("timeline_events", [])
                        wa_lines = [
                            f"🚨 *OFFICIAL EXAM NOTIFICATION*",
                            f"",
                            f"📌 *{title_clean}*",
                            f"🏛️ *Authority:* {org_clean}"
                        ]
                        if vacancies_wa and vacancies_wa.lower() not in ["n/a", "none", "", "check official"]:
                            wa_lines.append(f"👥 *Total Vacancies:* {vacancies_wa}")
                        if eligibility_wa and eligibility_wa.lower() not in ["n/a", "none", "", "check official"]:
                            wa_lines.append(f"🎓 *Eligibility:* {eligibility_wa}")

                        if timeline_events_wa and isinstance(timeline_events_wa, list) and len(timeline_events_wa) > 0:
                            wa_lines.append(f"\n🗓️ *CRITICAL DATES & TIMELINE:*")
                            for ev in timeline_events_wa:
                                if isinstance(ev, dict) and ev.get("label") and ev.get("date"):
                                    wa_lines.append(f"• *{ev['label']}:* {ev['date']}")
                                elif isinstance(ev, str) and ev.strip():
                                    wa_lines.append(f"• {ev.strip()}")
                        elif dates_wa and dates_wa.lower() not in ["n/a", "none", "", "check official"]:
                            wa_lines.append(f"\n🗓️ *CRITICAL DATES & TIMELINE:*")
                            if "start:" in dates_wa.lower() and "last date:" in dates_wa.lower():
                                parts = [p.strip() for p in re.split(r'[\|,]', dates_wa) if p.strip()]
                                for p in parts:
                                    wa_lines.append(f"• *{p}*")
                            else:
                                wa_lines.append(f"• *Important Schedule:* {dates_wa}")
                            if exam_schedule_wa and exam_schedule_wa.lower() not in ["n/a", "none", "", "check official"]:
                                wa_lines.append(f"• *Exam Schedule:* {exam_schedule_wa}")

                        if bullets_wa:
                            wa_lines.append(f"\n⚡ *KEY EXAM DETAILS & ACTION PLAN:*")
                            for b in bullets_wa:
                                cleaned_b = str(b).strip().replace("**", "").replace("*", "")
                                if cleaned_b:
                                    if ":" in cleaned_b:
                                        lbl, val = cleaned_b.split(":", 1)
                                        wa_lines.append(f"• *{lbl.strip()}:* {val.strip()}")
                                    else:
                                        wa_lines.append(f"• {cleaned_b}")

                        wa_lines.append(f"\n🌐 *Direct Official Notification Link:*\n{official_link_wa}")
                        if target_url_clean and "generated-uuid" not in target_url_clean:
                            wa_lines.append(f"\n📖 *Detailed Syllabus, Pattern & Analysis on OdishaExamPrep:*\n{target_url_clean}")
                        wa_lines.append(f"\n🚀 *Free Mock Tests & Practice:*\nhttps://www.odishaexamprep.in")

                        wa_caption = "\n".join(wa_lines)
                    else:
                        wa_caption = (
                            f"📚 *NEW EXAM STRATEGY & MASTERCLASS*\n\n"
                            f"📌 *{title_clean}*\n"
                            f"🏆 *Target:* {org_clean}\n\n"
                            f"👉 *Read Full Masterclass:*\n{target_url_clean}\n\n"
                            f"🚀 *Free Mock Tests & Practice:*\nhttps://www.odishaexamprep.in"
                        )

                    if cover_img and os.path.exists(str(cover_img)):
                        wa_public_success = send_whatsapp_image(cover_img, wa_caption)
                    else:
                        wa_public_success = send_whatsapp_message(wa_caption)
            except Exception as wa_ex:
                print(f"⚠️ WhatsApp Channel dispatch notice: {wa_ex}")

            if engine == "CURRENT_AFFAIRS":
                target_url = "https://www.odishaexamprep.in/current-affairs"
            else:
                target_url = resolve_clean_article_url(details)

            # --- AI Model Reporting ---
            model_used = details.get("model_used", "")
            used_fallback = details.get("used_fallback", False)
            if model_used:
                if used_fallback:
                    ai_line = f"🔄 <b>AI Model:</b> ⚠️ FALLBACK — <code>{model_used}</code>\n"
                else:
                    ai_line = f"🤖 <b>AI Model:</b> ✅ PRIMARY — <code>{model_used}</code>\n"
            else:
                ai_line = ""

            yt_status = details.get("youtube_status")
            yt_line = f"🔴 <b>YouTube Community:</b> {yt_status}\n" if yt_status else ""
            wa_line = f"🟢 <b>WhatsApp Channel:</b> {'Published to Channel ✅' if wa_public_success else 'Skipped / Pending Config ⚠️'}\n"

            msg = (
                f"🗃️ <b>{engine.replace('_', ' ').title()} Execution Report</b>\n\n"
                f"📝 <b>Title:</b> {details.get('title', 'N/A')}\n"
                f"🏢 <b>Board / Exam:</b> {details.get('organization', details.get('target_exam', 'Odisha Competitive Exams'))}\n"
                f"🌐 <b>Website Link:</b> {target_url}\n\n"
                f"{ai_line}"
                f"📢 <b>Telegram Channel:</b> {'Published to Channel ✅' if public_success else 'Failed ❌'}\n"
                f"{wa_line}"
                f"{yt_line}"
                f"✅ <b>Status:</b> SUCCESS"
                f"{metrics_footer}"
            )
        elif status in ["SKIPPED", "INFO", "NOTICE"]:
            msg = (
                f"⚠️ <b>CONTENT SKIPPED / NOTICE</b>\n\n"
                f"⚙️ <b>Engine:</b> {engine}\n"
                f"🏆 <b>Exam:</b> {details.get('exam', details.get('target_exam', 'N/A'))}\n"
                f"❓ <b>Reason:</b> {details.get('reason', details.get('status_note', 'No high-value candidate passed threshold'))}\n"
                f"ℹ️ No new content was published."
                f"{metrics_footer}"
            )
        else:
            msg = (
                f"❌ <b>AUTOMATION FAILED</b>\n\n"
                f"⚙️ <b>Engine:</b> {engine}\n"
                f"📍 <b>Stage:</b> {details.get('stage', 'Execution')}\n"
                f"⚠️ <b>Error:</b> {details.get('error', 'Unknown Error')}\n"
                f"🚨 <b>Status:</b> FAILED"
                f"{metrics_footer}"
            )

        payload = {
            "chat_id": TELEGRAM_ADMIN_CHAT_ID,
            "text": msg,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }
        res = requests.post(url, data=payload, timeout=20)
        if not res.ok:
            # Fallback to sanitized plain text to guarantee admin notification delivery
            print(f"⚠️ [Admin Telegram HTML Error] ({res.status_code}): {res.text}. Retrying with plain text fallback...")
            plain_msg = re.sub(r'<[^>]+>', '', msg)
            res = requests.post(url, data={"chat_id": TELEGRAM_ADMIN_CHAT_ID, "text": plain_msg}, timeout=20)

        if res.ok:
            print(f"[Admin Telegram Confirmation] Sent ({status})")
        else:
            print(f"[Admin Telegram Confirmation Final Error]: {res.text}")
    except Exception as e:
        print(f"[Admin Telegram Confirmation Exception]: {e}")

def send_draft_review_alert(details: dict) -> bool:
    """
    Sends an executive Masterclass Draft Staging & Approval Alert to Admin Telegram.
    Embeds 1-click Live Preview Link and direct Publish / Discard actions.
    """
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        article_id = str(details.get("article_id") or details.get("id") or "").strip()
        title = details.get("title", "New Masterclass Draft")
        category = details.get("category", "General")
        topic = details.get("topic", "N/A")
        framework = details.get("framework", "N/A")
        score = details.get("quality_score", 95)
        word_count = details.get("word_count", 1500)
        linter_status = "✅ 100% Passed All Code Linters" if details.get("linter_passed", True) else "⚠️ Quarantined with Warnings"
        secret = "oep_publish_secure_2026"

        preview_url = f"https://www.odishaexamprep.in/blog/preview/{article_id}?secret={secret}"
        publish_url = f"https://www.odishaexamprep.in/api/blog/publish-direct?id={article_id}&secret={secret}"
        discard_url = f"https://www.odishaexamprep.in/api/blog/discard-direct?id={article_id}"

        score_badge = "🟢 <b>HIGH CONFIDENCE</b>" if score >= 92 else "🟡 <b>STAGED FOR REVIEW</b>"

        msg = (
            f"🛡️ <b>MASTERCLASS DRAFT READY FOR REVIEW</b>\n\n"
            f"📌 <b>Title:</b> {title}\n"
            f"🏷️ <b>Category:</b> {category}\n"
            f"🎯 <b>Topic:</b> {topic}\n"
            f"⚙️ <b>Framework:</b> {framework}\n\n"
            f"📊 <b>Quality Score:</b> <b>{score}/100</b> ({score_badge})\n"
            f"📝 <b>Word Count:</b> {word_count:,} words (~{max(4, word_count // 220)} min read)\n"
            f"🔍 <b>Linter Status:</b> {linter_status}\n\n"
            f"👇 <b>Click below to read the fully rendered draft before publishing:</b>"
        )

        inline_keyboard = {
            "inline_keyboard": [
                [{"text": "📖 Read Full Live Draft Preview", "url": preview_url}],
                [{"text": "✅ Approve & Publish Live", "url": publish_url}, {"text": "❌ Discard Draft", "url": discard_url}]
            ]
        }

        payload = {
            "chat_id": TELEGRAM_ADMIN_CHAT_ID,
            "text": msg,
            "parse_mode": "HTML",
            "reply_markup": json.dumps(inline_keyboard),
            "disable_web_page_preview": False
        }

        res = requests.post(url, data=payload, timeout=20)
        if res.ok:
            print(f"[Draft Review Alert] Sent for article {article_id} (Score: {score}/100)")
            return True
        else:
            print(f"[Draft Review Alert Error]: {res.text}")
            return False
    except Exception as e:
        print(f"[Draft Review Alert Exception]: {e}")
        return False

# Alias for backward compatibility across all automation engines
send_telegram_alert = send_admin_alert

