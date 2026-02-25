import asyncio
import logging
from aiohttp import web
from telegram import Bot, Update
from telegram.error import TelegramError
from src import config, db, scheduler, bot as bot_module

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def health_check(request):
    return web.Response(text="OK", status=200)

async def webhook_handler(request):
    bot = request.app["bot"]
    try:
        update = Update.de_json(await request.json(), bot)
        await request.app["application"].process_update(update)
    except Exception as e:
        logger.error(f"Webhook error: {e}")
    return web.Response(text="OK", status=200)

async def register_webhook(bot: Bot):
    webhook_url = f"{config.RENDER_APP_URL}/webhook"
    try:
        current_webhook = await bot.get_webhook_info()
        if current_webhook.url != webhook_url:
            await bot.set_webhook(url=webhook_url)
            logger.info(f"Webhook set to {webhook_url}")
    except TelegramError as e:
        logger.error(f"Failed to set webhook: {e}")

async def on_startup(app):
    logger.info("Starting up...")
    
    config.validate_config()
    logger.info("Config validated")
    
    await db.init_db()
    logger.info("Database initialized")
    
    await scheduler.init_scheduler()
    logger.info("Scheduler initialized")
    
    app["application"] = bot_module.setup_bot()
    await app["application"].initialize()
    
    bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
    app["bot"] = bot
    
    await register_webhook(bot)
    
    await app["application"].start()
    #await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Bot started and webhook registered")

async def on_shutdown(app):
    logger.info("Shutting down...")
    
    if "application" in app:
        await app["application"].stop()
    
    await scheduler.shutdown_scheduler()
    await db.close_db()
    
    logger.info("Shutdown complete")

def create_app():
    app = web.Application()
    app.router.add_get("/health", health_check)
    app.router.add_post("/webhook", webhook_handler)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    return app

def main():
    app = create_app()
    port = config.PORT
    logger.info(f"Starting server on port {port}")
    web.run_app(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
