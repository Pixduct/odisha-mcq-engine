import os
import sys
import requests
import json

GREEN_API_ID_INSTANCE = os.getenv("GREEN_API_ID_INSTANCE", "710722716124")
GREEN_API_TOKEN_INSTANCE = os.getenv("GREEN_API_TOKEN_INSTANCE", "")
GREEN_API_HOST = os.getenv("GREEN_API_HOST", "https://7107.api.greenapi.com").rstrip("/")

def list_whatsapp_chats_and_channels(token=None):
    api_token = token or GREEN_API_TOKEN_INSTANCE
    if not api_token:
        print("❌ Error: GREEN_API_TOKEN_INSTANCE is required.")
        print("Usage: python discover_whatsapp_channels.py <YOUR_API_TOKEN_INSTANCE>")
        return

    url = f"{GREEN_API_HOST}/waInstance{GREEN_API_ID_INSTANCE}/getChats/{api_token}"
    print(f"🔍 Fetching chats and channels from GREEN-API ({url})...\n")

    try:
        res = requests.get(url, timeout=20)
        if not res.ok:
            print(f"❌ API Error HTTP {res.status_code}: {res.text}")
            return

        chats = res.json()
        print(f"✅ Retrieved {len(chats)} chats/channels.\n")
        print("=" * 60)
        print("📢 WHATSAPP CHANNELS (@newsletter):")
        print("=" * 60)
        channels_found = 0
        for c in chats:
            chat_id = c.get("id", "")
            name = c.get("name", "Unnamed")
            if "@newsletter" in chat_id:
                channels_found += 1
                print(f"👉 Channel Name: {name}")
                print(f"   Channel ID:   {chat_id}\n")

        if channels_found == 0:
            print("ℹ️ No @newsletter channels returned in getChats.")
            print("💡 Tip: If you just created the channel, post 1 message into your channel from your phone, then run this again.")

        print("=" * 60)
        print("👥 WHATSAPP GROUPS (@g.us):")
        print("=" * 60)
        for c in chats:
            chat_id = c.get("id", "")
            name = c.get("name", "Unnamed")
            if "@g.us" in chat_id:
                print(f"• Group: {name} (ID: {chat_id})")

    except Exception as e:
        print(f"❌ Network/Request Exception: {e}")

if __name__ == "__main__":
    passed_token = sys.argv[1] if len(sys.argv) > 1 else None
    list_whatsapp_chats_and_channels(passed_token)
