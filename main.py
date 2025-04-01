import os
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram import Router

# === ENV ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")  # https://cryptotradebot.onrender.com
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

# === INIT ===
bot = Bot(BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

# === HANDLERS ===
@router.message()
async def echo(message: types.Message):
    await message.answer("✅ Бот получил сообщение!")

# === WEBHOOK ===
async def handle_webhook(request):
    try:
        body = await request.json()
        update = types.Update(**body)
        await dp.feed_update(bot, update)
    except Exception as e:
        print(f"[Webhook Error] {e}")
    return web.Response(text="ok")

# === HEALTH ===
async def healthcheck(request):
    return web.Response(text="OK")

# === APP ===
app = web.Application()
app.router.add_post(WEBHOOK_PATH, handle_webhook)
app.router.add_get("/healthz", healthcheck)

# === START ===
async def on_startup():
    await bot.set_webhook(WEBHOOK_URL)
    print(f"✅ Webhook установлен: {WEBHOOK_URL}")

if __name__ == "__main__":
    async def main():
        await on_startup()
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", 8000)
        await site.start()
        print("🚀 Сервер запущен.")
        while True:
            await asyncio.sleep(3600)

    asyncio.run(main())
