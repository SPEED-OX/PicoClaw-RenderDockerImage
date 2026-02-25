import time
from datetime import datetime
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CommandHandler
from src import config, llm, search, scheduler, tasks, db

START_TIME = time.time()

def check_access(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    chat_id = update.effective_chat.id
    if not config.is_chat_allowed(chat_id):
        return False
    return True

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        await context.bot.send_message(chat_id=update.effective_chat.id, text="This is a personal bot, not authorized.")
        return
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="PicoClaw here. Personal assistant, Telegram-controlled.\n\n"
             "Commands:\n"
             "/start - this message\n"
             "/help - all commands\n"
             "/search <query> - web search\n"
             "/remind <time> <msg> - set reminder (30s, 10m, 2h, tomorrow 9am)\n"
             "/reminders - list active reminders\n"
             "/cancelreminder <id> - cancel reminder\n"
             "/run <command> - execute (ls, pwd, date, uptime, df, free, echo)\n"
             "/clear - clear conversation\n"
             "/model - show LLM model\n"
             "/status - bot status\n\n"
             "Or just message me directly."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        return
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Commands:\n"
             "/start - intro\n"
             "/help - this list\n"
             "/search <query> - web search + summary\n"
             "/remind <time> <msg> - set reminder\n"
             "/reminders - show active reminders\n"
             "/cancelreminder <id> - cancel by ID\n"
             "/run <cmd> - run whitelisted command\n"
             "/clear - clear chat history\n"
             "/model - current LLM\n"
             "/status - uptime & stats\n\n"
             "Any other message goes to the LLM."
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

async def run_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        return
    command = " ".join(context.args)
    if not command:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Usage: /run <command>")
        return
    
    output, success = await tasks.run_command(update.effective_chat.id, command)
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"```\n{output}\n```", parse_mode="MarkdownV2")

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        return
    await db.clear_conversation(update.effective_chat.id)
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Conversation cleared.")

async def model_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        return
    await context.bot.send_message(chat_id=update.effective_chat.id, text=f"Model: {config.OPENROUTER_MODEL}")

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
             f"Model: {config.OPENROUTER_MODEL}"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not check_access(update, context):
        return
    text = update.message.text
    
    if text.startswith("/"):
        return
    
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
    app.add_handler(CommandHandler("remind", remind_command))
    app.add_handler(CommandHandler("reminders", reminders_command))
    app.add_handler(CommandHandler("cancelreminder", cancel_reminder_command))
    app.add_handler(CommandHandler("run", run_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("model", model_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    return app
