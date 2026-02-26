import os
import json
import re
from typing import List, Dict, Any, Optional

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
RENDER_APP_URL = os.getenv("RENDER_APP_URL", "").rstrip("/")
PORT = int(os.getenv("PORT", "8080"))
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

EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
SMTP_SERVER = os.getenv("SMTP_SERVER", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
IMAP_SERVER = os.getenv("IMAP_SERVER", "")

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME", "")

def resolve_env_vars(value: Any) -> Any:
    if isinstance(value, str):
        pattern = r'\$\{([^}]+)\}'
        def replace_env_var(match):
            env_var = match.group(1)
            return os.getenv(env_var, "")
        return re.sub(pattern, replace_env_var, value)
    elif isinstance(value, dict):
        return {k: resolve_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [resolve_env_vars(item) for item in value]
    return value

def load_config() -> Dict[str, Any]:
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.json")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            config = json.load(f)
        return resolve_env_vars(config)
    return {}

BOT_CONFIG = load_config()

PROVIDERS = BOT_CONFIG.get("providers", {})
AGENTS = BOT_CONFIG.get("agents", {})
ROUTING = BOT_CONFIG.get("routing", {})
BOT_SETTINGS = BOT_CONFIG.get("bot", {})

DEFAULT_PROVIDER = AGENTS.get("default", {}).get("provider", "openrouter")
DEFAULT_MODEL = AGENTS.get("default", {}).get("model", "mistralai/mistral-7b-instruct:free")
CLASSIFIER_MODEL = ROUTING.get("classifier_model", "openrouter/mistralai/mistral-7b-instruct:free")

REQUIRED_VARS = [
    "TELEGRAM_BOT_TOKEN",
    "RENDER_APP_URL",
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

def get_provider_config(provider_name: str) -> Optional[Dict[str, Any]]:
    return PROVIDERS.get(provider_name)

def get_agent_config(agent_name: str) -> Optional[Dict[str, Any]]:
    return AGENTS.get(agent_name)

def get_all_models() -> List[str]:
    models = []
    for provider_name, provider_config in PROVIDERS.items():
        for model_entry in provider_config.get("models", []):
            if isinstance(model_entry, dict):
                model_id = model_entry.get("id", "")
            else:
                model_id = str(model_entry)
            if model_id:
                models.append(f"{provider_name}/{model_id}")
    return models
