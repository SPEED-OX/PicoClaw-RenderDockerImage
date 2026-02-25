import time
import json
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CommandHandler
from src import config, llm, search, scheduler, tasks, db, shortcuts, browser, notes, email_handler, github_handler

START_TIME = time.time()

def check_access(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat_id = update.effective_chat.id
    return config.is_chat_allowed(chat_id)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        return
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="PicoClaw here. Personal assistant, Telegram-controlled.\n\n"
             "Commands: /help\n\n"
             "Or just message me directly."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        return
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Commands:\n"
             "/start - Introduction message\n"
             "/help - List all available commands\n"
             "/search <query> - Search the web and get an LLM summary\n"
             "/browse <url> - Fetch a URL and summarize its content\n"
             "/remind <time> <msg> - Set a reminder (e.g., 10m, 2h, tomorrow 9)\n"
             "/reminders - List all active reminders\n"
             "/cancelreminder <id> - Cancel a reminder by ID\n"
             "/note <text> - Save a note\n"
             "/notes - List all saved notes\n"
             "/deletenote <id> - Delete a note by ID\n"
             "/run <command> - Execute a whitelisted shell command\n"
             "/model - View current model\n"
             "/model <provider/model> - Override model for this session\n"
             "/model list - List all available models\n"
             "/model reset - Clear model override\n"
             "/agent <name> - Force a specific agent\n"
             "/agent reset - Return to auto-routing\n"
             "/shortcut add <trigger> <expansion> - Create a command shortcut\n"
             "/shortcut list - List all shortcuts\n"
             "/shortcut remove <trigger> - Delete a shortcut\n"
             "/config - View bot configuration\n"
             "/session - View session state\n"
             "/session reset - Reset session overrides\n"
             "/clear - Clear conversation history\n"
             "/status - Bot uptime and stats\n"
             "/email <to> <subject> <body> - Send an email\n"
             "/inbox - Check last 5 unread emails\n"
             "/gh repos - List GitHub repositories\n"
             "/gh issues <repo> - List open issues for a repo\n"
             "/gh commits <repo> - List recent commits for a repo\n\n"
             "Any message goes to the LLM."
    )

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        return
    query = " ".join(context.args)
    if not query:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Usage: /search <query>")
        return
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Searching...")
    result = await search.search_web(query)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=result)

async def browse_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        return
    url = " ".join(context.args)
    if not url:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Usage: /browse <url>")
        return
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Fetching...")
    result = await browser.browse_url(url)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=result)

async def remind_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        return
    args = context.args
    if len(args) < 2:
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text="Usage: /remind <time> <message>\nExamples: /remind 10m Call mom, /remind tomorrow 9am"
        )
        return
    time_str = args[0]
    message = " ".join(args[1:])
    remind_at = scheduler.parse_time(time_str)
    if not remind_at:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Invalid time format. Use: 30s, 10m, 2h, tomorrow 9am, or 14:30"
        )
        return
    if remind_at <= datetime.now():
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Time must be in the future.")
        return
    reminder_id = await scheduler.schedule_reminder(update.effective_chat.id, message, remind_at)
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Reminder set for {remind_at.strftime('%Y-%m-%d %H:%M')}. ID: {reminder_id}"
    )

async def reminders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        return
    reminders = await db.get_all_reminders(update.effective_chat.id)
    if not reminders:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No active reminders.")
        return
    lines = ["Active reminders:"]
    for r in reminders:
        remind_at = r["remind_at"]
        if isinstance(remind_at, str):
            remind_at = datetime.fromisoformat(remind_at)
        lines.append(f"• {r['id']}: {r['message']} at {remind_at.strftime('%Y-%m-%d %H:%M')}")
    await context.bot.send_message(chat_id=update.effective_chat.id, text="\n".join(lines))

async def cancel_reminder_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        return
    if not context.args:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Usage: /cancelreminder <id>")
        return
    try:
        reminder_id = int(context.args[0])
    except ValueError:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Invalid reminder ID.")
        return
    await db.delete_reminder(reminder_id)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Reminder {reminder_id} cancelled.")

async def note_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        return
    content = " ".join(context.args)
    if not content:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Usage: /note <text>")
        return
    note_id = await notes.add_note(update.effective_chat.id, content)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Note saved. ID: {note_id}")

async def notes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        return
    note_list = await notes.get_notes(update.effective_chat.id)
    if not note_list:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="No notes saved.")
        return
    lines = ["Your notes:"]
    for n in note_list:
        lines.append(f"• {n['id']}: {n['content'][:50]}...")
    await context.bot.send_message(chat_id=update.effective_chat.id, text="\n".join(lines))

async def deletenote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        return
    if not context.args:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Usage: /deletenote <id>")
        return
    try:
        note_id = int(context.args[0])
    except ValueError:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Invalid note ID.")
        return
    await notes.delete_note(update.effective_chat.id, note_id)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Note {note_id} deleted.")

async def run_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        return
    command = " ".join(context.args)
    if not command:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Usage: /run <command>")
        return
    output, success = await tasks.run_command(update.effective_chat.id, command)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"```\n{output}\n```", parse_mode="MarkdownV2")

async def model_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        return
    args = context.args
    chat_id = update.effective_chat.id
    
    if not args:
        session = await db.get_session(chat_id)
        current = session.get("model_override") or config.DEFAULT_MODEL
        await context.bot.send_message(chat_id=chat_id, text=f"Current model: {current}")
        return
    
    if args[0] == "reset":
        await db.update_session(chat_id, model_override=None)
        await context.bot.send_message(chat_id=chat_id, text="Model override cleared.")
        return
    
    if args[0] == "list":
        models = config.get_all_models()
        await context.bot.send_message(chat_id=chat_id, text="Available models:\n" + "\n".join(models))
        return
    
    model = args[0]
    await db.update_session(chat_id, model_override=model)
    await context.bot.send_message(chat_id=chat_id, text=f"Model set to: {model}")

async def agent_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        return
    args = context.args
    chat_id = update.effective_chat.id
    
    if not args:
        session = await db.get_session(chat_id)
        current = session.get("agent_override") or "auto (keyword routing)"
        await context.bot.send_message(chat_id=chat_id, text=f"Current agent: {current}")
        return
    
    if args[0] == "reset":
        await db.update_session(chat_id, agent_override=None)
        await context.bot.send_message(chat_id=chat_id, text="Agent override cleared.")
        return
    
    agent_name = args[0]
    if agent_name not in config.AGENTS:
        await context.bot.send_message(chat_id=chat_id, text=f"Unknown agent. Available: {', '.join(config.AGENTS.keys())}")
        return
    
    await db.update_session(chat_id, agent_override=agent_name)
    await context.bot.send_message(chat_id=chat_id, text=f"Agent set to: {agent_name}")

async def shortcut_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        return
    args = context.args
    chat_id = update.effective_chat.id
    
    if not args:
        shortcut_list = await db.get_shortcuts(chat_id)
        if not shortcut_list:
            await context.bot.send_message(chat_id=chat_id, text="No shortcuts. Usage: /shortcut add /gm 'Good morning'")
            return
        lines = ["Your shortcuts:"]
        for s in shortcut_list:
            lines.append(f"{s['trigger']} → {s['expansion'][:30]}...")
        await context.bot.send_message(chat_id=chat_id, text="\n".join(lines))
        return
    
    if args[0] == "add":
        if len(args) < 3:
            await context.bot.send_message(chat_id=chat_id, text="Usage: /shortcut add /gm 'Good morning, summarize my emails'")
            return
        trigger = args[1]
        expansion = " ".join(args[2:]).strip("'\"")
        await db.add_shortcut(chat_id, trigger, expansion)
        await context.bot.send_message(chat_id=chat_id, text=f"Shortcut added: {trigger}")
        return
    
    if args[0] == "remove":
        trigger = args[1] if len(args) > 1 else ""
        if not trigger:
            await context.bot.send_message(chat_id=chat_id, text="Usage: /shortcut remove /gm")
            return
        await db.delete_shortcut(chat_id, trigger)
        await context.bot.send_message(chat_id=chat_id, text=f"Shortcut removed: {trigger}")
        return
    
    if args[0] == "list":
        shortcut_list = await db.get_shortcuts(chat_id)
        if not shortcut_list:
            await context.bot.send_message(chat_id=chat_id, text="No shortcuts.")
            return
        lines = ["Your shortcuts:"]
        for s in shortcut_list:
            lines.append(f"{s['trigger']} → {s['expansion'][:30]}...")
        await context.bot.send_message(chat_id=chat_id, text="\n".join(lines))
        return

async def config_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        return
    bot_config = config.BOT_SETTINGS
    safe_config = {
        "name": bot_config.get("name"),
        "personality": bot_config.get("personality"),
        "max_history": bot_config.get("max_history"),
        "commands_count": len(bot_config.get("commands", [])),
    }
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Bot config:\n{json.dumps(safe_config, indent=2)}"
    )

async def session_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        return
    args = context.args
    chat_id = update.effective_chat.id
    
    if args and args[0] == "reset":
        await db.reset_session(chat_id)
        await context.bot.send_message(chat_id=chat_id, text="Session reset.")
        return
    
    session = await db.get_session(chat_id)
    lines = [
        "Session state:",
        f"Model override: {session.get('model_override') or 'none'}",
        f"Agent override: {session.get('agent_override') or 'none'}",
        f"Messages: {session.get('message_count', 0)}",
    ]
    await context.bot.send_message(chat_id=chat_id, text="\n".join(lines))

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        return
    await db.clear_conversation(update.effective_chat.id)
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Conversation cleared.")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        return
    uptime = int(time.time() - START_TIME)
    hours, remainder = divmod(uptime, 3600)
    minutes, seconds = divmod(remainder, 60)
    pending = await db.get_pending_reminders()
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Uptime: {hours}h {minutes}m {seconds}s\n"
             f"Pending reminders: {len(pending)}\n"
             f"Default model: {config.DEFAULT_MODEL}"
    )

async def email_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        return
    args = context.args
    if len(args) < 3:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Usage: /email <to> <subject> <body>")
        return
    to = args[0]
    subject = args[1]
    body = " ".join(args[2:])
    result = await email_handler.send_email(to, subject, body)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=result)

async def inbox_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        return
    result = await email_handler.get_inbox()
    await context.bot.send_message(chat_id=update.effective_chat.id, text=result)

async def gh_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        return
    args = context.args
    if not args:
        result = await github_handler.list_repos()
        await context.bot.send_message(chat_id=update.effective_chat.id, text=result)
        return
    
    action = args[0]
    repo = args[1] if len(args) > 1 else ""
    
    if action == "repos":
        result = await github_handler.list_repos()
    elif action == "issues" and repo:
        result = await github_handler.list_issues(repo)
    elif action == "commits" and repo:
        result = await github_handler.recent_commits(repo)
    else:
        result = "Usage: /gh repos | /gh issues <repo> | /gh commits <repo>"
    
    await context.bot.send_message(chat_id=update.effective_chat.id, text=result)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        return
    text = update.message.text
    
    if text.startswith("/"):
        return
    
    expanded = await shortcuts.expand_shortcut(update.effective_chat.id, text)
    if expanded:
        text = expanded
    
    response = await llm.call_llm(update.effective_chat.id, text)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=response)

async def send_reminder_message(chat_id: int, message: str):
    from telegram import Bot
    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    await bot.send_message(chat_id=chat_id, text=f"🔔 Reminder: {message}")

def setup_bot():
    scheduler.set_reminder_callback(send_reminder_message)
    
    app = ApplicationBuilder().token(config.TELEGRAM_BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("browse", browse_command))
    app.add_handler(CommandHandler("remind", remind_command))
    app.add_handler(CommandHandler("reminders", reminders_command))
    app.add_handler(CommandHandler("cancelreminder", cancel_reminder_command))
    app.add_handler(CommandHandler("note", note_command))
    app.add_handler(CommandHandler("notes", notes_command))
    app.add_handler(CommandHandler("deletenote", deletenote_command))
    app.add_handler(CommandHandler("run", run_command))
    app.add_handler(CommandHandler("model", model_command))
    app.add_handler(CommandHandler("agent", agent_command))
    app.add_handler(CommandHandler("shortcut", shortcut_command))
    app.add_handler(CommandHandler("config", config_command))
    app.add_handler(CommandHandler("session", session_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("email", email_command))
    app.add_handler(CommandHandler("inbox", inbox_command))
    app.add_handler(CommandHandler("gh", gh_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    return app
