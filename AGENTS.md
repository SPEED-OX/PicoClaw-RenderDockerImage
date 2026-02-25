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
1. **Answer questions** — using LLM via OpenRouter API
2. **Run tasks** — execute shell commands, scripts, or predefined automations
3. **Reminders & scheduling** — set reminders, notify user at the right time
4. **Search the web** — fetch and summarize web results for the user

---

## Tech Stack

| Layer | Technology |
|---|---|
| Bot interface | Telegram Bot API (python-telegram-bot v20+) |
| Webhook server | aiohttp |
| LLM brain | OpenRouter API (model configurable via env) |
| Web search | DuckDuckGo Search (free, no API key needed) — `duckduckgo-search` lib |
| Scheduler | APScheduler (for reminders) |
| Database | MySQL (cPanel hosting) via aiomysql |
| Backend | Python 3.11 |
| Container | Docker |
| Hosting | Render.com (free tier, Web Service) |
| Config | Environment variables |

---

## Project File Structure

```
picoclaw/
├── AGENTS.md                  ← You are here
├── Dockerfile                 ← Container definition
├── requirements.txt           ← All dependencies
├── .env.example               ← Env vars template (no secrets)
├── render.yaml                ← Render one-click deploy config
└── src/
    ├── main.py                ← Entry point: starts aiohttp webhook server
    ├── bot.py                 ← Telegram handlers, command routing
    ├── config.py              ← Loads and validates all env vars
    ├── db.py                  ← MySQL database (aiomysql), conversation history, reminders, logs
    ├── llm.py                 ← OpenRouter API calls, conversation context
    ├── search.py              ← DuckDuckGo web search + summarization
    ├── scheduler.py           ← APScheduler reminders logic (loads from DB on startup)
    └── tasks.py               ← Task/command execution logic
```

---

## Core Features

### 1. LLM Brain (llm.py)
- Calls OpenRouter API (`https://openrouter.ai/api/v1/chat/completions`)
- Model is set via `OPENROUTER_MODEL` env var (default: `mistralai/mistral-7b-instruct:free`)
- Maintains per-chat conversation history stored in MySQL (last N messages via MAX_HISTORY)
- System prompt defines PicoClaw's personality and capabilities
- Used as fallback for any message that isn't a specific command

### 2. Web Search (search.py)
- Uses `duckduckgo-search` Python lib (free, no key needed)
- Triggered by `/search <query>` or when LLM decides search is needed
- Returns top 3 results, summarized by LLM before sending to user

### 3. Reminders (scheduler.py)
- Uses APScheduler with AsyncIOScheduler
- `/remind <time> <message>` — e.g. `/remind 10m Call mom`
- Supports: `30s`, `10m`, `2h`, `tomorrow 9am`
- Sends Telegram message to user when reminder fires
- Reminders stored in MySQL, loaded on startup (persistent across restarts)

### 4. Task Execution (tasks.py)
- `/run <command>` — executes shell command inside container
- Output returned to user via Telegram (truncated if too long)
- Restricted to a whitelist of safe commands defined in config
- Agent must implement a `ALLOWED_COMMANDS` list for security

### 5. Conversation (bot.py)
- Any plain message (no command prefix) goes to LLM brain
- LLM has full context of recent conversation
- PicoClaw's personality: helpful, concise, direct, no unnecessary fluff

---

## Telegram Commands

| Command | Action |
|---|---|
| `/start` | Intro message, list capabilities |
| `/help` | Show all commands |
| `/search <query>` | Web search + summarize |
| `/remind <time> <msg>` | Set a reminder |
| `/reminders` | List active reminders |
| `/cancelreminder <id>` | Cancel a reminder |
| `/run <command>` | Execute whitelisted shell command |
| `/clear` | Clear conversation history for this chat |
| `/model` | Show current LLM model in use |
| `/status` | Show bot uptime, reminders count, memory usage |

Any message without a `/` prefix is treated as a chat message to the LLM.

---

## Webhook Architecture

- Render Web Service receives Telegram updates via webhook
- `POST /webhook` → routes to bot.py handler
- `GET /health` → returns 200 OK (required by Render)
- On startup, `main.py` auto-registers webhook URL with Telegram

```
User → Telegram → POST /webhook → bot.py → llm.py / search.py / scheduler.py → reply
```

---

## Docker Setup

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
EXPOSE 8080
CMD ["python", "src/main.py"]
```

---

## Render Deployment

- Service type: **Web Service**
- Runtime: Docker
- Free tier
- Deploy on push to `main` branch
- `render.yaml` must be present for one-click deploy

```yaml
services:
  - type: web
    name: picoclaw
    runtime: docker
    plan: free
    envVars:
      - key: TELEGRAM_BOT_TOKEN
        sync: false
      - key: RENDER_APP_URL
        sync: false
      - key: OPENROUTER_API_KEY
        sync: false
      - key: OPENROUTER_MODEL
        value: mistralai/mistral-7b-instruct:free
      - key: PORT
        value: "8080"
      - key: ALLOWED_CHAT_IDS
        sync: false
```

---

## Environment Variables

```
TELEGRAM_BOT_TOKEN=        # From @BotFather
RENDER_APP_URL=            # e.g. https://picoclaw.onrender.com (no trailing slash)
PORT=8080                  # Render injects this, keep as fallback
OPENROUTER_API_KEY=        # From openrouter.ai (free account)
OPENROUTER_MODEL=mistralai/mistral-7b-instruct:free  # Swap anytime
ALLOWED_CHAT_IDS=          # Your Telegram chat ID (owner only access)
MAX_HISTORY=20             # Max messages kept in conversation context

# MySQL Database (cPanel hosting)
MYSQL_HOST=                # Database host
MYSQL_PORT=3306            # Database port
MYSQL_USER=                # Database username
MYSQL_PASSWORD=            # Database password
MYSQL_DB=                  # Database name
```

---

## Security

- `ALLOWED_CHAT_IDS` — only whitelisted Telegram IDs can use the bot
- Every handler must check chat ID before processing
- `/run` command uses `ALLOWED_COMMANDS` whitelist, never open shell
- No secrets ever hardcoded or logged

---

## Agent Rules & Constraints

1. **No game logic, no simulation** — this is a real assistant
2. **No paid services** — OpenRouter free models, DuckDuckGo free search
3. **Webhook only** — no polling
4. **Single container** — one Dockerfile, one Render service
5. **Python only** — no Node, no Go
6. **Secrets via env only** — never hardcode or log tokens
7. **PORT from env** — always `os.getenv("PORT", 8080)`
8. **Health check required** — `GET /health` must return 200
9. **Owner-only access** — always validate `ALLOWED_CHAT_IDS`
10. **Graceful errors** — all exceptions caught, user gets a friendly error message

---

## What the Agent Should Build (In Order)

1. `src/config.py` — env var loader + validator
2. `src/db.py` — MySQL database (aiomysql), conversation history, reminders, logs
3. `src/llm.py` — OpenRouter API client + conversation history
4. `src/search.py` — DuckDuckGo search + LLM summarization
5. `src/scheduler.py` — APScheduler reminders (loads from DB on startup)
6. `src/tasks.py` — whitelisted command execution
7. `src/bot.py` — all Telegram handlers wired together
8. `src/main.py` — aiohttp server, webhook registration, startup
9. `requirements.txt` — all dependencies pinned
10. `Dockerfile` — lean Python 3.11 container
11. `render.yaml` — Render Web Service config
12. `.env.example` — all vars with comments

---

## What the User Configures Later

- [ ] `TELEGRAM_BOT_TOKEN` — from @BotFather
- [ ] `OPENROUTER_API_KEY` — from openrouter.ai (free account)
- [ ] `RENDER_APP_URL` — available after first Render deploy
- [ ] `ALLOWED_CHAT_IDS` — your personal Telegram chat ID
- [ ] `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DB` — cPanel MySQL credentials
- [ ] Swap `OPENROUTER_MODEL` to a better model per task (future)
- [ ] More task automations in `tasks.py` (future scope)

---

## Success Criteria

The project is "done" when:
- `docker build` succeeds
- `GET /health` returns 200
- Bot replies to a plain message via LLM
- `/search hello world` returns summarized results
- `/remind 1m test` fires after 1 minute
- Only the owner's chat ID can use the bot
- Deploys to Render free tier without modification

---

*Last updated: Feb 2026 | Maintained by: Project Owner*