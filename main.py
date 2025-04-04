import asyncio
import json
import logging
import os
from datetime import datetime
from smtplib import SMTP, SMTP_SSL
from email.message import EmailMessage

from aiogram import Bot, Dispatcher, types, F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application, setup_webhook
from aiohttp import web
from openpyxl import Workbook

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()
router = Router()
dp.include_router(router)

# Переменные окружения
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")

# ... (остальной код)

async def main():
    app = web.Application()
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path="/webhook")
    setup_application(app, dp, bot=bot)
    app.router.add_get("/healthz", healthcheck)
    app.router.add_get("/", handle_root)
    dp.startup.register(on_startup)

    # Изменения здесь
    await setup_webhook(bot, webhook_path="/webhook", webapp_host=WEBHOOK_HOST, webapp_port=int(os.environ.get("PORT", 8080)))

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 8080)))
    await site.start()
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
    
