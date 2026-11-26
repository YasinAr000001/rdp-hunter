import os

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
CHANNEL_USERNAMES = os.getenv("CHANNEL_USERNAMES", "")
SESSION_NAME = os.getenv("SESSION_NAME", "rdp_hunter")
SAVED_MESSAGES_RAW = os.getenv("SAVED_MESSAGES", "me")
try:
    SAVED_MESSAGES = int(SAVED_MESSAGES_RAW)
except ValueError:
    SAVED_MESSAGES = SAVED_MESSAGES_RAW
PHONE_NUMBER = os.getenv("PHONE_NUMBER", "")
STRING_SESSION = os.getenv("STRING_SESSION", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Password generation
PASSWORD_LENGTH = 14
SPECIAL_CHARS = "!@#$%^&*"

# Impacket settings
SMB_TIMEOUT = 5
MAX_RETRIES = 2

# Duplicate tracking
CACHE_FILE = "caught.json"


def get_channels():
    if not CHANNEL_USERNAMES:
        return []
    return [c.strip() for c in CHANNEL_USERNAMES.split(",") if c.strip()]