import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, types, Router
from aiogram.filters import CommandStart
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота и диспетчера
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()
router = Router()
dp.include_router(router)

# Переменные окружения
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")

# Обработчик команды /start
@router.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer("Бот работает!")

async def main():
    app = web.Application()
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path="/webhook")
    setup_application(app, dp, bot=bot)
    return app

if __name__ == "__main__":
    app = asyncio.run(main())
    web.run_app(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
