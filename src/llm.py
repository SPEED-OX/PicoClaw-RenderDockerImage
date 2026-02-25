import httpx
import json
from typing import List, Dict, Any, Optional
from src import config, db

SYSTEM_PROMPT = """You are PicoClaw, a capable personal assistant. You are concise, sharp, and direct. No fluff. No chatbot mannerisms. You get things done.

Capabilities:
- Answer questions accurately
- Execute commands: ls, pwd, date, uptime, df, free, echo
- Set reminders
- Search the web when needed
- Run shell commands when requested

Always be helpful but efficient. Don't be verbose unless the task requires it."""


async def get_conversation_messages(chat_id: int) -> List[Dict[str, str]]:
    history = await db.get_conversation_history(chat_id)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    return messages


async def call_llm(chat_id: int, user_message: str) -> str:
    messages = await get_conversation_messages(chat_id)
    messages.append({"role": "user", "content": user_message})

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": config.RENDER_APP_URL or "http://localhost",
                    "X-Title": "PicoClaw",
                },
                json={
                    "model": config.OPENROUTER_MODEL,
                    "messages": messages,
                },
            )
            response.raise_for_status()
            data = response.json()
            try:
                assistant_reply = data["choices"][0]["message"]["content"]
            except (KeyError, IndexError):
                assistant_reply = "No response from model."

            await db.add_message(chat_id, "user", user_message)
            await db.add_message(chat_id, "assistant", assistant_reply)

            return assistant_reply
        except httpx.HTTPStatusError as e:
            return f"Error: LLM API returned {e.response.status_code}"
        except Exception as e:
            return f"Error: {str(e)}"


async def summarize_with_llm(prompt: str) -> str:
    messages = [
        {"role": "system", "content": "You summarize web search results concisely. Be brief."},
        {"role": "user", "content": prompt}
    ]

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": config.RENDER_APP_URL or "http://localhost",
                    "X-Title": "PicoClaw",
                },
                json={
                    "model": config.OPENROUTER_MODEL,
                    "messages": messages,
                },
            )
            response.raise_for_status()
            data = response.json()
            try:
                return data["choices"][0]["message"]["content"]
            except (KeyError, IndexError):
                return "No response from model."
        except Exception as e:
            return f"Summary error: {str(e)}"
