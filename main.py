import os
from aiohttp import web

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")  # https://cryptotradebot.onrender.com
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage

bot = Bot(BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Простой echo-хендлер
@dp.message()
async def echo(message: types.Message):
    await message.answer(f"Ты сказал: {message.text}")

# Webhook endpoint
async def handle_webhook(request):
    try:
        data = await request.json()
        update = types.Update(**data)
        await dp.feed_update(bot, update)
        print("✅ Update получен")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    return web.Response(text="OK")

# Healthcheck
async def healthcheck(request):
    return web.Response(text="OK")

# Приложение aiohttp
app = web.Application()
app.router.add_post(WEBHOOK_PATH, handle_webhook)
app.router.add_get("/healthz", healthcheck)

# Установка вебхука при запуске
async def on_startup():
    await bot.set_webhook(WEBHOOK_URL)
    print(f"🚀 Webhook установлен: {WEBHOOK_URL}")

# Запуск
if __name__ == "__main__":
    import asyncio
    async def main():
        await on_startup()
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", 8000)
        await site.start()
        print("🌐 Сервер запущен на 0.0.0.0:8000")
        while True:
            await asyncio.sleep(3600)

    asyncio.run(main())
