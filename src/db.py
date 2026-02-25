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
                if pool:
                    async with pool.acquire() as conn:
                        await conn.ping(reconnect=True)
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

    create_sessions_table = """
    CREATE TABLE IF NOT EXISTS sessions (
        id INT AUTO_INCREMENT PRIMARY KEY,
        chat_id BIGINT NOT NULL UNIQUE,
        model_override VARCHAR(255),
        agent_override VARCHAR(255),
        message_count INT DEFAULT 0,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_chat_id (chat_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """

    create_notes_table = """
    CREATE TABLE IF NOT EXISTS notes (
        id INT AUTO_INCREMENT PRIMARY KEY,
        chat_id BIGINT NOT NULL,
        content TEXT NOT NULL,
        tags VARCHAR(255),
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_chat_id (chat_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """

    create_shortcuts_table = """
    CREATE TABLE IF NOT EXISTS shortcuts (
        id INT AUTO_INCREMENT PRIMARY KEY,
        chat_id BIGINT NOT NULL,
        `trigger` VARCHAR(255) NOT NULL,
        expansion TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_chat_id (chat_id),
        UNIQUE KEY unique_trigger (chat_id, `trigger`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """

    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(create_conversation_table)
            await cur.execute(create_reminders_table)
            await cur.execute(create_command_logs_table)
            await cur.execute(create_sessions_table)
            await cur.execute(create_notes_table)
            await cur.execute(create_shortcuts_table)

async def close_db():
    global pool
    if pool:
        try:
            pool.close()
            await pool.wait_closed()
        except Exception:
            pass

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

@retry_on_operational_error
async def get_session(chat_id: int) -> Dict[str, Any]:
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT model_override, agent_override, message_count FROM sessions WHERE chat_id = %s",
                (chat_id,)
            )
            row = await cur.fetchone()
            if row:
                return dict(row)
            await cur.execute(
                "INSERT INTO sessions (chat_id) VALUES (%s)",
                (chat_id,)
            )
            return {"model_override": None, "agent_override": None, "message_count": 0}

@retry_on_operational_error
async def update_session(chat_id: int, model_override: Optional[str] = None, agent_override: Optional[str] = None):
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            if model_override is not None:
                await cur.execute(
                    "INSERT INTO sessions (chat_id, model_override) VALUES (%s, %s) ON DUPLICATE KEY UPDATE model_override = %s",
                    (chat_id, model_override, model_override)
                )
            if agent_override is not None:
                await cur.execute(
                    "INSERT INTO sessions (chat_id, agent_override) VALUES (%s, %s) ON DUPLICATE KEY UPDATE agent_override = %s",
                    (chat_id, agent_override, agent_override)
                )
            await cur.execute(
                "UPDATE sessions SET message_count = message_count + 1 WHERE chat_id = %s",
                (chat_id,)
            )

@retry_on_operational_error
async def reset_session(chat_id: int):
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE sessions SET model_override = NULL, agent_override = NULL, message_count = 0 WHERE chat_id = %s",
                (chat_id,)
            )

@retry_on_operational_error
async def add_note(chat_id: int, content: str, tags: Optional[str] = None) -> int:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO notes (chat_id, content, tags) VALUES (%s, %s, %s)",
                (chat_id, content, tags)
            )
            return cur.lastrowid

@retry_on_operational_error
async def get_notes(chat_id: int) -> List[Dict[str, Any]]:
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT id, content, tags, created_at FROM notes WHERE chat_id = %s ORDER BY created_at DESC",
                (chat_id,)
            )
            return await cur.fetchall()

@retry_on_operational_error
async def delete_note(note_id: int, chat_id: int):
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM notes WHERE id = %s AND chat_id = %s",
                (note_id, chat_id)
            )

@retry_on_operational_error
async def search_notes(chat_id: int, query: str) -> List[Dict[str, Any]]:
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT id, content, tags, created_at FROM notes WHERE chat_id = %s AND (content LIKE %s OR tags LIKE %s) ORDER BY created_at DESC",
                (chat_id, f"%{query}%", f"%{query}%")
            )
            return await cur.fetchall()

@retry_on_operational_error
async def add_shortcut(chat_id: int, trigger: str, expansion: str) -> int:
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO shortcuts (chat_id, `trigger`, expansion) VALUES (%s, %s, %s) ON DUPLICATE KEY UPDATE expansion = %s",
                (chat_id, trigger, expansion, expansion)
            )
            return cur.lastrowid

@retry_on_operational_error
async def get_shortcuts(chat_id: int) -> List[Dict[str, Any]]:
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT id, `trigger`, expansion, created_at FROM shortcuts WHERE chat_id = %s ORDER BY created_at DESC",
                (chat_id,)
            )
            return await cur.fetchall()

@retry_on_operational_error
async def get_shortcut(chat_id: int, trigger: str) -> Optional[Dict[str, Any]]:
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT id, `trigger`, expansion FROM shortcuts WHERE chat_id = %s AND `trigger` = %s",
                (chat_id, trigger)
            )
            row = await cur.fetchone()
            return dict(row) if row else None

@retry_on_operational_error
async def delete_shortcut(chat_id: int, trigger: str):
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM shortcuts WHERE chat_id = %s AND `trigger` = %s",
                (chat_id, trigger)
            )
