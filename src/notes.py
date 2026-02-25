from typing import List, Optional
from src import db

async def add_note(chat_id: int, content: str, tags: Optional[str] = None) -> int:
    return await db.add_note(chat_id, content, tags)

async def get_notes(chat_id: int) -> List[dict]:
    return await db.get_notes(chat_id)

async def delete_note(chat_id: int, note_id: int):
    await db.delete_note(note_id, chat_id)

async def search_notes(chat_id: int, query: str) -> List[dict]:
    return await db.search_notes(chat_id, query)
