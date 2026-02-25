import os
from typing import List

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
RENDER_APP_URL = os.getenv("RENDER_APP_URL", "").rstrip("/")
PORT = int(os.getenv("PORT", "8080"))
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "mistralai/mistral-7b-instruct:free")
MAX_HISTORY = int(os.getenv("MAX_HISTORY", "20"))

ALLOWED_CHAT_IDS_STR = os.getenv("ALLOWED_CHAT_IDS", "")
ALLOWED_CHAT_IDS: List[int] = []
if ALLOWED_CHAT_IDS_STR:
    try:
        ALLOWED_CHAT_IDS = [int(x.strip()) for x in ALLOWED_CHAT_IDS_STR.split(",")]
    except ValueError:
        pass

ALLOWED_COMMANDS = ["ls", "pwd", "date", "uptime", "df", "free", "echo"]

MYSQL_HOST = os.getenv("MYSQL_HOST", "")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DB = os.getenv("MYSQL_DB", "")

REQUIRED_VARS = [
    "TELEGRAM_BOT_TOKEN",
    "RENDER_APP_URL",
    "OPENROUTER_API_KEY",
    "ALLOWED_CHAT_IDS",
    "MYSQL_HOST",
    "MYSQL_USER",
    "MYSQL_PASSWORD",
    "MYSQL_DB",
]

def validate_config():
    missing = [var for var in REQUIRED_VARS if not os.getenv(var, "")]
    if missing:
        raise ValueError(f"Missing required env vars: {', '.join(missing)}")
    return True

def is_chat_allowed(chat_id: int) -> bool:
    return chat_id in ALLOWED_CHAT_IDS
