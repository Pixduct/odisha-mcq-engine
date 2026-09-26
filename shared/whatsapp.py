import os
import time
import requests

# Green API Credentials & Endpoint Configuration
GREEN_API_ID_INSTANCE = os.getenv("GREEN_API_ID_INSTANCE", "710722716124")
GREEN_API_TOKEN_INSTANCE = os.getenv("GREEN_API_TOKEN_INSTANCE", "")
GREEN_API_HOST = os.getenv("GREEN_API_HOST", "https://7107.api.greenapi.com").rstrip("/")
WHATSAPP_CHANNEL_ID = os.getenv("WHATSAPP_CHANNEL_ID", "120363412784897729@g.us")

def is_whatsapp_configured() -> bool:
    """Returns True if Green API instance and channel ID are configured."""
    return bool(GREEN_API_ID_INSTANCE and GREEN_API_TOKEN_INSTANCE and WHATSAPP_CHANNEL_ID)

def send_whatsapp_message(text: str, chat_id: str = None) -> bool:
    """
    Sends a text message to a WhatsApp Channel (@newsletter), Group (@g.us), or Direct Chat (@c.us).
    """
    target_chat = chat_id or WHATSAPP_CHANNEL_ID
    if not target_chat or not GREEN_API_TOKEN_INSTANCE:
        print("ℹ️ [WhatsApp] Skipping: GREEN_API_TOKEN_INSTANCE or WHATSAPP_CHANNEL_ID not configured.")
        return False

    url = f"{GREEN_API_HOST}/waInstance{GREEN_API_ID_INSTANCE}/sendMessage/{GREEN_API_TOKEN_INSTANCE}"
    payload = {
        "chatId": target_chat,
        "message": text
    }

    for attempt in range(1, 4):
        try:
            res = requests.post(url, json=payload, timeout=20)
            if res.ok:
                chat_type = "Channel (@newsletter)" if target_chat.endswith("@newsletter") else ("Group (@g.us)" if target_chat.endswith("@g.us") else "Direct Chat (@c.us)")
                print(f"✅ [WhatsApp] Message posted successfully to {target_chat} [{chat_type}] (attempt {attempt})")
                return True
            else:
                print(f"⚠️ [WhatsApp] API HTTP {res.status_code}: {res.text}. Attempt {attempt}/3")
                time.sleep(2 * attempt)
        except Exception as ex:
            print(f"⚠️ [WhatsApp] Network error on attempt {attempt}/3: {ex}")
            time.sleep(2 * attempt)

    return False

def send_whatsapp_image(image_path: str, caption: str = "", chat_id: str = None) -> bool:
    """
    Uploads and sends an image with caption to a WhatsApp Channel (@newsletter) or Group (@g.us).
    """
    target_chat = chat_id or WHATSAPP_CHANNEL_ID
    if not target_chat or not GREEN_API_TOKEN_INSTANCE:
        print("ℹ️ [WhatsApp] Skipping: GREEN_API_TOKEN_INSTANCE or WHATSAPP_CHANNEL_ID not configured.")
        return False

    if not os.path.exists(image_path):
        print(f"⚠️ [WhatsApp] Image file not found: {image_path}")
        return False

    url = f"{GREEN_API_HOST}/waInstance{GREEN_API_ID_INSTANCE}/sendFileByUpload/{GREEN_API_TOKEN_INSTANCE}"
    
    file_name = os.path.basename(image_path)
    data = {
        "chatId": target_chat,
        "caption": caption,
        "fileName": file_name
    }

    for attempt in range(1, 4):
        try:
            with open(image_path, "rb") as f:
                files = {
                    "file": (file_name, f, "image/png")
                }
                res = requests.post(url, data=data, files=files, timeout=30)
                if res.ok:
                    chat_type = "Channel (@newsletter)" if target_chat.endswith("@newsletter") else ("Group (@g.us)" if target_chat.endswith("@g.us") else "Direct Chat (@c.us)")
                    print(f"✅ [WhatsApp] Image '{file_name}' posted successfully to {target_chat} [{chat_type}]")
                    return True
                else:
                    print(f"⚠️ [WhatsApp] File upload API HTTP {res.status_code}: {res.text}. Attempt {attempt}/3")
                    time.sleep(2 * attempt)
        except Exception as ex:
            print(f"⚠️ [WhatsApp] Image upload error on attempt {attempt}/3: {ex}")
            time.sleep(2 * attempt)

    return False

def send_whatsapp_media_group(image_paths: list, caption: str = "", chat_id: str = None) -> bool:
    """
    Sends multiple images in sequence to WhatsApp Channel.
    First image contains the rich formatted caption. Subsequent images follow.
    """
    if not image_paths:
        return False

    success_all = True
    # Send first image with caption
    first_ok = send_whatsapp_image(image_paths[0], caption=caption, chat_id=chat_id)
    if not first_ok:
        success_all = False

    # Send remaining images with brief delay
    for img in image_paths[1:]:
        time.sleep(1.5)
        ok = send_whatsapp_image(img, caption="", chat_id=chat_id)
        if not ok:
            success_all = False

    return success_all
