import os
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message

# === Переменные окружения ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")  # например: https://cryptotradebot.onrender.com
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# === Инициализация ===
bot = Bot(BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# === Базовый хендлер ===
@dp.message()
async def echo(message: Message):
    print("📩 Получено сообщение от пользователя")
    await message.answer("✅ Бот работает через Webhook!")

# === Обработка webhook ===
async def handle_webhook(request):
    try:
        print("📬 Webhook вызван")
        data = await request.json()
        update = types.Update(**data)
        await dp.feed_update(bot, update)
    except Exception as e:
        print(f"[Webhook error] {e}")
    return web.Response(text="OK")

# === Healthcheck ===
async def healthcheck(request):
    print("🔍 Healthcheck вызван")
    return web.Response(text="OK")

# === Создание aiohttp-приложения ===
app = web.Application()
app.router.add_post(WEBHOOK_PATH, handle_webhook)
app.router.add_get("/healthz", healthcheck)

# === Старт вебхука ===
async def on_startup():
    await bot.set_webhook(WEBHOOK_URL)
    print(f"🚀 Webhook установлен по адресу: {WEBHOOK_URL}")

# === Запуск ===
if __name__ == "__main__":
    async def main():
        await on_startup()
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host="0.0.0.0", port=8000)
        await site.start()
        print("🌐 Сервер aiohttp запущен и слушает порт 8000")

        # Ожидание в фоне
        while True:
            await asyncio.sleep(3600)

    asyncio.run(main())
