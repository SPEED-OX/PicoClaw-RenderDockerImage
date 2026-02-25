import re
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Callable, Awaitable
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from src import config, db

scheduler = AsyncIOScheduler()

ReminderCallback = Callable[[int, str], Awaitable[None]]

send_reminder: Optional[ReminderCallback] = None

def set_reminder_callback(callback: ReminderCallback):
    global send_reminder
    send_reminder = callback

def parse_time(time_str: str) -> Optional[datetime]:
    now = datetime.now()
    time_str = time_str.strip().lower()

    patterns = [
        (r"^(\d+)s$", lambda m: now + timedelta(seconds=int(m.group(1)))),
        (r"^(\d+)m$", lambda m: now + timedelta(minutes=int(m.group(1)))),
        (r"^(\d+)h$", lambda m: now + timedelta(hours=int(m.group(1)))),
        (r"^(\d+)d$", lambda m: now + timedelta(days=int(m.group(1)))),
    ]

    for pattern, parser in patterns:
        match = re.match(pattern, time_str)
        if match:
            return parser(match)

    tomorrow_match = re.match(r"^tomorrow\s+(\d{1,2})(?::(\d{2}))?$", time_str)
    if tomorrow_match:
        hour = int(tomorrow_match.group(1))
        minute = int(tomorrow_match.group(2) or 0)
        tomorrow = now + timedelta(days=1)
        return tomorrow.replace(hour=hour, minute=minute, second=0, microsecond=0)

    today_match = re.match(r"^(\d{1,2})(?::(\d{2}))$", time_str)
    if today_match:
        hour = int(today_match.group(1))
        minute = int(today_match.group(2) or 0)
        result = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if result <= now:
            result += timedelta(days=1)
        return result

    return None

async def schedule_reminder(chat_id: int, message: str, remind_at: datetime) -> int:
    reminder_id = await db.add_reminder(chat_id, message, remind_at)

    job_id = f"reminder_{reminder_id}"
    scheduler.add_job(
        fire_reminder,
        DateTrigger(run_date=remind_at),
        args=[reminder_id, chat_id, message],
        id=job_id,
        replace_existing=True
    )
    return reminder_id

async def fire_reminder(reminder_id: int, chat_id: int, message: str):
    if send_reminder:
        try:
            await send_reminder(chat_id, message)
        except Exception as e:
            print(f"Error sending reminder: {e}")
    try:
        await db.delete_reminder(reminder_id)
    except Exception as e:
        print(f"Error deleting reminder: {e}")

async def load_pending_reminders():
    try:
        pending = await db.get_pending_reminders()
        for r in pending:
            reminder_id = r["id"]
            chat_id = r["chat_id"]
            message = r["message"]
            remind_at = r["remind_at"]

            if isinstance(remind_at, str):
                remind_at = datetime.fromisoformat(remind_at)

            if remind_at > datetime.now():
                job_id = f"reminder_{reminder_id}"
                scheduler.add_job(
                    fire_reminder,
                    DateTrigger(run_date=remind_at),
                    args=[reminder_id, chat_id, message],
                    id=job_id,
                    replace_existing=True
                )
                print(f"Loaded reminder {reminder_id} for chat {chat_id}")
    except Exception as e:
        print(f"Error loading pending reminders: {e}")

async def init_scheduler():
    if not scheduler.running:
        scheduler.start()
    await load_pending_reminders()

async def shutdown_scheduler():
    if scheduler.running:
        scheduler.shutdown()
