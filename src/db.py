import aiomysql
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Callable, TypeVar
from src import config

pool: Optional[aiomysql.Pool] = None

def retry_on_operational_error(func):
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except aiomysql.OperationalError:
            try:
                return await func(*args, **kwargs)
            except aiomysql.OperationalError:
                raise
    return wrapper

async def init_db():
    global pool
    pool = await aiomysql.create_pool(
        host=config.MYSQL_HOST,
        port=config.MYSQL_PORT,
        user=config.MYSQL_USER,
        password=config.MYSQL_PASSWORD,
        db=config.MYSQL_DB,
        autocommit=True,
        minsize=1,
        maxsize=5,
    )
    await create_tables()

async def create_tables():
    create_conversation_table = """
    CREATE TABLE IF NOT EXISTS conversation_history (
        id INT AUTO_INCREMENT PRIMARY KEY,
        chat_id BIGINT NOT NULL,
        role ENUM('user', 'assistant') NOT NULL,
        content TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_chat_id (chat_id),
        INDEX idx_timestamp (timestamp)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """

    create_reminders_table = """
    CREATE TABLE IF NOT EXISTS reminders (
        id INT AUTO_INCREMENT PRIMARY KEY,
        chat_id BIGINT NOT NULL,
        message TEXT NOT NULL,
        remind_at DATETIME NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_chat_id (chat_id),
        INDEX idx_remind_at (remind_at)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """

    create_command_logs_table = """
    CREATE TABLE IF NOT EXISTS command_logs (
        id INT AUTO_INCREMENT PRIMARY KEY,
        chat_id BIGINT NOT NULL,
        command VARCHAR(255) NOT NULL,
        output TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_chat_id (chat_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(create_conversation_table)
            await cur.execute(create_reminders_table)
            await cur.execute(create_command_logs_table)

async def close_db():
    global pool
    if pool:
        pool.close()
        await pool.wait_closed()

@retry_on_operational_error
async def add_message(chat_id: int, role: str, content: str):
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO conversation_history (chat_id, role, content) VALUES (%s, %s, %s)",
                (chat_id, role, content)
            )

@retry_on_operational_error
async def get_conversation_history(chat_id: int, limit: int = None) -> List[Dict[str, Any]]:
    if limit is None:
        limit = config.MAX_HISTORY * 2
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                """SELECT role, content FROM conversation_history 
                   WHERE chat_id = %s 
                   ORDER BY timestamp DESC LIMIT %s""",
                (chat_id, limit)
            )
            rows = await cur.fetchall()
            return list(reversed(rows))

@retry_on_operational_error
async def clear_conversation(chat_id: int):
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM conversation_history WHERE chat_id = %s",
                (chat_id,)
            )

@retry_on_operational_error
async def add_reminder(chat_id: int, message: str, remind_at: datetime) -> int:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO reminders (chat_id, message, remind_at) VALUES (%s, %s, %s)",
                (chat_id, message, remind_at)
            )
            return cur.lastrowid

@retry_on_operational_error
async def get_pending_reminders() -> List[Dict[str, Any]]:
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT id, chat_id, message, remind_at FROM reminders WHERE remind_at > NOW() ORDER BY remind_at"
            )
            return await cur.fetchall()

@retry_on_operational_error
async def delete_reminder(reminder_id: int):
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("DELETE FROM reminders WHERE id = %s", (reminder_id,))

@retry_on_operational_error
async def get_all_reminders(chat_id: int) -> List[Dict[str, Any]]:
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT id, message, remind_at FROM reminders WHERE chat_id = %s AND remind_at > NOW() ORDER BY remind_at",
                (chat_id,)
            )
            return await cur.fetchall()

@retry_on_operational_error
async def log_command(chat_id: int, command: str, output: str):
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO command_logs (chat_id, command, output) VALUES (%s, %s, %s)",
                (chat_id, command, output)
            )
    await cleanup_old_logs(chat_id)

@retry_on_operational_error
async def cleanup_old_logs(chat_id: int, days: int = 30):
    cutoff = datetime.now() - timedelta(days=days)
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM command_logs WHERE chat_id = %s AND created_at < %s",
                (chat_id, cutoff)
            )
