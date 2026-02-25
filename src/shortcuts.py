from typing import Optional, List, Dict, Any
from src import db

async def expand_shortcut(chat_id: int, message: str) -> Optional[str]:
    for shortcut in await db.get_shortcuts(chat_id):
        if message.strip() == shortcut["trigger"]:
            return shortcut["expansion"]
    return None

async def add_shortcut(chat_id: int, trigger: str, expansion: str) -> int:
    return await db.add_shortcut(chat_id, trigger, expansion)

async def list_shortcuts(chat_id: int) -> List[Dict[str, Any]]:
    return await db.get_shortcuts(chat_id)

async def remove_shortcut(chat_id: int, trigger: str):
    await db.delete_shortcut(chat_id, trigger)
