from typing import Optional
from src import db

async def expand_shortcut(chat_id: int, message: str) -> Optional[str]:
    for shortcut in await db.get_shortcuts(chat_id):
        if message.strip() == shortcut["trigger"]:
            return shortcut["expansion"]
    return None
