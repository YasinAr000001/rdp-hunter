#!/usr/bin/env python3
"""
Run this ONCE locally (Termux) to generate STRING_SESSION.
Then copy the output to Railway Variables.
"""
import os
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from config import API_ID, API_HASH, PHONE_NUMBER


async def main():
    if API_ID == 0 or not API_HASH:
        print("❌ Set API_ID and API_HASH in config.py or env")
        return
    
    if not PHONE_NUMBER:
        print("❌ Set PHONE_NUMBER in config.py or env (e.g., +8801XXXXXXXXX)")
        return
    
    client = TelegramClient(StringSession(), API_ID, API_HASH)
    
    print("[*] Connecting...")
    await client.connect()
    
    if not await client.is_user_authorized():
        print("[*] Sending code to", PHONE_NUMBER)
        await client.send_code_request(PHONE_NUMBER)
        code = input("Enter code from Telegram: ")
        try:
            await client.sign_in(PHONE_NUMBER, code)
        except Exception as e:
            print(f"❌ Login failed: {e}")
            return
    
    string_session = client.session.save()
    print("\n" + "="*60)
    print("STRING_SESSION (copy this to Railway Variables):")
    print("="*60)
    print(string_session)
    print("="*60)
    print("\nAdd to Railway Variables as STRING_SESSION")
    print("Then deploy — no phone prompt needed!")


if __name__ == "__main__":
    asyncio.run(main())