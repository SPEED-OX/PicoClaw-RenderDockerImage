# AGENTS.md — PicoClaw Personal Assistant
> This file is the single source of truth for any AI agent working on this project.
> Read this fully before writing any code, creating any file, or making any decision.

---

## What Is This Project?

**PicoClaw** is a personal AI assistant agent controlled entirely via **Telegram**.
It runs in a Docker container hosted on **Render.com (free tier)**.
The user interacts with it through Telegram messages — PicoClaw thinks, acts, and responds.

This is NOT a game. This is NOT a claw machine simulation.
This is a personal productivity agent.

---

## Goal

Build a Telegram-based personal assistant that can:
1. **Answer questions** — using LLM via configurable providers (OpenRouter, Groq, Google, DeepSeek)
2. **Run tasks** — execute shell commands, scripts, or predefined automations
3. **Reminders & scheduling** — set reminders, notify user at the right time
4. **Search the web** — fetch and summarize web results for the user
5. **Browse URLs** — fetch and summarize any webpage
6. **Manage notes** — save, list, delete notes per chat
7. **Shortcuts** — create custom command shortcuts
8. **Email** — send emails and check inbox (via SMTP/IMAP)
9. **GitHub** — list repos, issues, commits via GitHub API

---

## Tech Stack

| Layer | Technology |
|---|---|
| Bot interface | Telegram Bot API (python-telegram-bot v20+) |
| Webhook server | aiohttp |
| LLM brain | Multi-provider (OpenRouter, Groq, Google, DeepSeek) via config.json |
| Web search | DuckDuckGo Search — `duckduckgo-search` lib |
| URL browsing | httpx + BeautifulSoup |
| Scheduler | APScheduler (for reminders) |
| Database | MySQL (cPanel hosting) via aiomysql |
| Backend | Python 3.11 |
| Container | Docker |
| Hosting | Render.com (free tier, Web Service) |
| Config | config.json + Environment variables |

---

## Provider System

PicoClaw supports multiple LLM providers via config.json:

- **OpenRouter** — free models available
- **Groq** — fast inference
- **Google** — Gemini models
- **DeepSeek** — reasoning models

Each provider has an API key loaded from env vars, resolved at runtime via `${ENV_VAR_NAME}` placeholders in config.json.

---

## Agent Router

Hybrid routing system:
1. **Keyword matching** — predefined keywords map to agents (reason, search, creative)
2. **LLM classifier** — if no keyword match, uses LLM to classify message into an agent

Agents:
- `default` — general conversation
- `reason` — analytical questions
- `search` — web search tasks
- `creative` — writing tasks

Each agent has a primary provider/model and a fallback for reliability.

---

## Project File Structure

```
picoclaw/
├── AGENTS.md                  ← You are here
├── config.json                ← Providers, agents, routing, bot settings
├── Dockerfile                 ← Container definition
├── requirements.txt           ← All dependencies
├── .env.example               ← Env vars template (no secrets)
├── render.yaml                ← Render one-click deploy config
└── src/
    ├── main.py               ← Entry point: aiohttp webhook server
    ├── bot.py                ← Telegram handlers, all command routing
    ├── config.py             ← Loads config.json + env vars
    ├── db.py                 ← MySQL: history, reminders, notes, shortcuts, sessions
    ├── providers.py          ← Multi-provider abstraction layer
    ├── agent_router.py       ← Task routing + agent execution
    ├── llm.py               ← Wrapper for agent_router
    ├── search.py            ← DuckDuckGo web search
    ├── browser.py           ← URL fetching + summarization
    ├── notes.py             ← Notes management
    ├── shortcuts.py         ← Command shortcuts expansion
    ├── scheduler.py         ← APScheduler reminders (loads from DB on startup)
    ├── tasks.py             ← Whitelisted shell command execution
    ├── email_handler.py     ← SMTP send + IMAP inbox
    └── github_handler.py    ← GitHub REST API operations
```

---

## Database Schema (MySQL)

- **conversation_history** — per-chat message history (MAX_HISTORY pairs per chat)
- **reminders** — persistent reminders (persistent until fired or cancelled)
- **command_logs** — whitelisted command logs (30-day rolling retention per chat_id)
- **sessions** — per-chat model/agent overrides, message counts
- **notes** — per-chat notes with tags
- **shortcuts** — per-chat command shortcuts (trigger → expansion)

---

## Telegram Commands

| Command | Action |
|---|---|
| `/start` | Intro message |
| `/help` | Show all commands |
| `/search <query>` | Web search + summarize |
| `/browse <url>` | Fetch and summarize URL |
| `/remind <time> <msg>` | Set a reminder |
| `/reminders` | List active reminders |
| `/cancelreminder <id>` | Cancel a reminder |
| `/note <text>` | Save a note |
| `/notes` | List all notes |
| `/deletenote <id>` | Delete a note |
| `/run <command>` | Execute whitelisted command |
| `/model` | View current model |
| `/model <provider/model>` | Override model for session |
| `/model reset` | Clear model override |
| `/model list` | List available models |
| `/agent <name>` | Force specific agent |
| `/agent reset` | Back to auto routing |
| `/shortcut add <trigger> <expansion>` | Create shortcut |
| `/shortcut list` | List shortcuts |
| `/shortcut remove <trigger>` | Delete shortcut |
| `/config` | View bot configuration |
| `/session` | View session state |
| `/clear` | Clear conversation history |
| `/status` | Bot uptime, stats |
| `/email <to> <subject> <body>` | Send email |
| `/inbox` | Check unread emails |
| `/gh` | GitHub operations |

Any message without a `/` prefix is treated as a chat message to the LLM.

---

## Webhook Architecture

```
User → Telegram → POST /webhook → bot.py → agent_router → providers → reply
```

- `POST /webhook` — receives Telegram updates
- `GET /health` — returns 200 OK (required by Render)
- On startup, `main.py` auto-registers webhook URL with Telegram
- On startup, `main.py` registers all commands with Telegram (inline suggestions)

---

## Docker Setup

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
COPY config.json ./
ENV PYTHONPATH=/app
EXPOSE 8080
CMD ["python", "-m", "src.main"]
```

---

## Render Deployment

- Service type: **Web Service**
- Runtime: **Docker**
- Free tier
- Deploy on push to `main` branch

---

## Environment Variables

```
TELEGRAM_BOT_TOKEN=        # From @BotFather
RENDER_APP_URL=            # e.g. https://picoclaw.onrender.com (no trailing slash)
PORT=8080                  # Render injects this, keep as fallback
ALLOWED_CHAT_IDS=          # Your Telegram chat ID (owner only access)
MAX_HISTORY=20             # Max message pairs per chat

# MySQL Database (cPanel)
MYSQL_HOST=
MYSQL_PORT=3306
MYSQL_USER=
MYSQL_PASSWORD=
MYSQL_DB=

# Provider API Keys (see config.json)
OPENROUTER_API_KEY=
GROQ_API_KEY=
GOOGLE_API_KEY=
DEEPSEEK_API_KEY=

# Email (optional)
EMAIL_ADDRESS=
EMAIL_PASSWORD=
SMTP_SERVER=
SMTP_PORT=587
IMAP_SERVER=

# GitHub (optional)
GITHUB_TOKEN=
GITHUB_USERNAME=
```

---

## config.json Structure

```json
{
  "providers": {
    "openrouter": { "api_key": "${OPENROUTER_API_KEY}", "base_url": "...", "models": [...] },
    "groq": { "api_key": "${GROQ_API_KEY}", "base_url": "...", "models": [...] },
    ...
  },
  "agents": {
    "default": { "provider": "openrouter", "model": "...", "fallback": "..." },
    "reason": { "provider": "deepseek", "model": "...", "fallback": "..." },
    ...
  },
  "routing": {
    "keywords": { "reason": [...], "search": [...], "creative": [...] },
    "llm_classifier": true,
    "classifier_model": "..."
  },
  "bot": {
    "name": "PicoClaw",
    "personality": "...",
    "max_history": 20,
    "commands": [...]
  }
}
```

---

## Security

- `ALLOWED_CHAT_IDS` — only whitelisted Telegram IDs can use the bot
- Every handler must check chat ID before processing
- `/run` command uses `ALLOWED_COMMANDS` whitelist, never open shell
- No secrets ever hardcoded or logged
- API keys stored in environment, resolved via `${ENV_VAR}` placeholders in config.json

---

## Agent Rules & Constraints

1. **No game logic, no simulation** — this is a real assistant
2. **Webhook only** — no polling
3. **Single container** — one Dockerfile, one Render service
4. **Python only** — no Node, no Go
5. **Secrets via env only** — never hardcode or log tokens
6. **PORT from env** — always `os.getenv("PORT", 8080)`
7. **Health check required** — `GET /health` must return 200
8. **Owner-only access** — always validate `ALLOWED_CHAT_IDS`
9. **Graceful errors** — all exceptions caught, user gets friendly error message

---

## What Works On Render Free Tier

- Telegram bot with webhook
- Multi-provider LLM (OpenRouter, Groq, Google, DeepSeek)
- Web search (DuckDuckGo)
- URL browsing + summarization
- Notes and shortcuts
- Reminders (stored in MySQL, loaded on startup)
- GitHub API operations
- Command execution (whitelisted)

**Limited on Free Tier:**
- No email sending (SMTP often blocked)
- No custom tool installations
- Sleeps after 15 min inactivity

---

## Future Scope (VPS Migration)

When migrating to a VPS:
1. Install system packages for additional tools
2. Implement code execution agents (sandboxed)
3. Add file management capabilities
4. Implement more advanced agents
5. Add voice input/output
6. Implement custom plugin system

---

## Known Fixes & Decisions

1. **db.py: MySQL reconnect resilience** — Added retry decorator that retries once on OperationalError to handle cPanel idle disconnects.

2. **search.py: DDGS instantiation** — Moved DDGS() instantiation inside search_web() function so a failure doesn't crash the bot on import.

3. **scheduler.py: Async job execution** — Added `executor='asyncio'` to AsyncIOScheduler to ensure async reminder jobs fire reliably.

4. **bot.py: Silent reject unauthorized users** — Removed reply to unauthorized chat IDs - returns False silently without leaking that the bot exists.

5. **llm.py: Empty choices guard** — Wrapped `data["choices"][0]["message"]["content"]` in try/except with fallback "No response from model." to prevent KeyError crashes.

6. **tasks.py: Timeout placement** — Fixed asyncio.wait_for to wrap process.communicate() instead of create_subprocess_shell() so timeout actually triggers.

7. **tasks.py/db.py: Command log cleanup** — Added cleanup_old_logs() function that deletes logs older than 30 days per chat_id, called after each log_command() insert.

---

## Development Commands

### Setup & Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
# Edit .env with your credentials
```

### Running the Bot Locally

```bash
# Set required env vars first, then run:
python -m src.main

# Or with Docker:
docker build -t picoclaw .
docker run -p 8080:8080 --env-file .env picoclaw
```

### Testing & Linting

**Currently, this project has no formal test suite or linting configuration.**

If you add tests, use this workflow:

```bash
# Install test dependencies (example)
pip install pytest pytest-asyncio aiohttp-test-utils

# Run all tests
pytest

# Run a single test file
pytest tests/test_bot.py

# Run a single test function
pytest tests/test_bot.py::test_start_command

# Run with verbose output
pytest -v

# Run tests matching a pattern
pytest -k "test_search"

# Check code formatting
pip install black
black --check src/

# Check linting
pip install ruff
ruff check src/

# Run both
black src/ && ruff check src/
```

---

## Code Style Guidelines

This project follows Python best practices with some specific conventions.

### General Principles

- **Async-first**: Use `async`/`await` for all I/O operations (database, HTTP, Telegram API)
- **Type hints**: Always use type hints for function parameters and return types
- **Error handling**: Catch exceptions gracefully, never leak stack traces to users
- **No secrets**: Never hardcode secrets; use environment variables via `config.py`

### Imports

```python
# Standard library first, then third-party, then local
import os
import json
from datetime import datetime
from typing import List, Dict, Optional, Any

from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes

from src import config, db, llm
```

- Use explicit relative imports within the `src` package: `from src import config`
- Group imports by type (stdlib, third-party, local) with blank lines between
- Sort imports alphabetically within each group

### Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Functions/variables | snake_case | `def get_user(id):`, `max_history = 20` |
| Classes | PascalCase | `class MyHandler:` |
| Constants | UPPER_SNAKE | `MAX_HISTORY = 20` |
| Async functions | prefix with `async_` if ambiguous | `async def fetch_data()` |

### Type Hints

Always use type hints. Import from `typing` for complex types:

```python
from typing import List, Dict, Optional, Any, Callable

def process_items(items: List[str]) -> Dict[str, int]:
    return {item: len(item) for item in items}

async def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    ...
```

### Async/Await

```python
# Correct: async function
async def fetch_data(url: str) -> str:
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.text()

# Correct: calling async from sync context requires event loop
# In bot.py handlers, always await:
async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = await search.search_web(query)  # await the call
```

### Error Handling

```python
# Always wrap external calls in try/except
async def safe_operation():
    try:
        result = await risky_call()
        return result
    except SpecificException as e:
        logger.warning(f"Operation failed: {e}")
        return fallback_value
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return "An error occurred. Please try again."

# Never expose raw exceptions to users
try:
    await bot.send_message(chat_id=chat_id, text=message)
except Exception as e:
    await bot.send_message(chat_id=chat_id, text="Failed to send message.")
```

### Database Operations

```python
# Always use the retry decorator for DB operations
from src.db import retry_on_operational_error

@retry_on_operational_error
async def get_user(user_id: int):
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            return await cur.fetchone()

# Always use parameterized queries, never string formatting
# Wrong: cur.execute(f"SELECT * FROM users WHERE id = {user_id}")
# Correct: cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
```

### Telegram Bot Handlers

```python
# Always check access first
async def my_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        return  # Silently reject unauthorized users
    
    # Then process command
    await context.bot.send_message(chat_id=update.effective_chat.id, text="...")
```

### Configuration

- All configuration goes in `config.json` and `config.py`
- Secrets come from environment variables
- Use `${ENV_VAR_NAME}` syntax in `config.json` for env var resolution

### Logging

```python
import logging

logger = logging.getLogger(__name__)

# Use appropriate log levels
logger.debug("Detailed debug info")
logger.info("Normal operation")
logger.warning("Something unexpected but handled")
logger.error("Something failed")
```

---

## Adding New Features

1. **New command**: Add handler in `bot.py`, register in `main.py`
2. **New provider**: Add config in `config.json`, implement in `providers.py`
3. **New agent**: Add config in `config.json`, implement logic in `agent_router.py`
4. **Database table**: Add schema in `db.py::create_tables()`, add CRUD in `db.py`

---

## Debugging Tips

- Set `TELEGRAM_BOT_TOKEN` to test locally without deploying
- Use `python -m src.main` with DEBUG logging to see requests
- Check Render logs for production issues: `render logs -f <service>`
- Test webhook locally with ngrok: `ngrok http 8080`

---

*Last updated: Feb 2026 | Maintained by: Project Owner*
