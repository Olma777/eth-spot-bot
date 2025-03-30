import os
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.methods import GetWebhookInfo

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# === Хендлер команды /start
@dp.message(commands=["start"])
async def start(message: types.Message):
    await message.answer("✅ Бот работает. Webhook получен.")

# === Обработка webhook
async def handle_webhook(request):
    data = await request.json()
    update = types.Update(**data)
    await dp.feed_update(bot, update)
    return web.Response()

# === Healthcheck
async def healthcheck(request):
    return web.Response(text="OK")

# === Запуск
async def on_startup():
    await bot.set_webhook(WEBHOOK_URL)
    print(f"🚀 Webhook установлен: {WEBHOOK_URL}")

app = web.Application()
app.router.add_post(WEBHOOK_PATH, handle_webhook)
app.router.add_get("/healthz", healthcheck)

loop = asyncio.get_event_loop()
loop.run_until_complete(on_startup())
web.run_app(app, host="0.0.0.0", port=8000)
