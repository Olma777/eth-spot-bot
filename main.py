import os
import json
import openpyxl
import smtplib
from aiohttp import web
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders

from aiogram import Bot, Dispatcher, types, Router
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import GetWebhookInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# === Переменные окружения ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")  # https://cryptotradebot.onrender.com
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
SUPPORTED_TOKENS = ["ETH", "DOT", "AVAX", "RENDER"]

# === Инициализация ===
bot = Bot(BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)
scheduler = AsyncIOScheduler()

# === FSM ===
class EmailReport(StatesGroup):
    waiting_for_email = State()

selected_token = {}

# === Excel ===
def load_data(token):
    try:
        with open(f"{token}.json", "r") as f:
            return json.load(f)
    except:
        return {"avg_price": 0, "eth_total": 0, "usdt_total": 0, "history": []}

def export_to_excel(token):
    data = load_data(token)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"{token}_history"
    ws.append(["Дата", "Тип", "Цена", "Кол-во"])
    for entry in data["history"]:
        ws.append([entry.get("time", "-"), entry["action"], entry["price"], entry["amount"]])
    filename = f"{token}_history.xlsx"
    wb.save(filename)
    return filename

# === Email ===
async def send_email_with_attachment(to_email, subject, body, file_path):
    msg = MIMEMultipart()
    msg["From"] = SMTP_USER
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    part = MIMEBase("application", "octet-stream")
    with open(file_path, "rb") as f:
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f'attachment; filename="{os.path.basename(file_path)}"')
    msg.attach(part)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)

# === Хендлеры ===
@router.message()
async def handle_message(message: types.Message, state: FSMContext):
    if message.text == "/send_email":
        buttons = [[InlineKeyboardButton(text=t, callback_data=f"send:{t}")] for t in SUPPORTED_TOKENS]
        markup = InlineKeyboardMarkup(inline_keyboard=buttons)
        await message.answer("Выбери токен:", reply_markup=markup)

    elif message.text == "/webhook_info":
        info = await bot(GetWebhookInfo())
        await message.answer(f"Webhook URL: {info.url or 'не установлен'}")

@router.callback_query()
async def callbacks(call: types.CallbackQuery, state: FSMContext):
    if call.data.startswith("send:"):
        token = call.data.split(":")[1]
        selected_token[call.from_user.id] = token
        await call.message.answer("Введите email:")
        await state.set_state(EmailReport.waiting_for_email)

@router.message(EmailReport.waiting_for_email)
async def get_email(message: types.Message, state: FSMContext):
    email = message.text.strip()
    token = selected_token.get(message.from_user.id)
    file_path = export_to_excel(token)
    try:
        await send_email_with_attachment(email, f"Отчёт по {token}", "Отчёт прилагается.", file_path)
        await message.answer(f"✅ Отчёт по {token} отправлен на {email}")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
    await state.clear()

# === Webhook ===
async def handle_webhook(request):
    try:
        body = await request.json()
        update = types.Update(**body)
        await dp.feed_update(bot, update)
        print("📩 Получено обновление от Telegram")
    except Exception as e:
        print(f"[Webhook Error] {e}")
    return web.Response(text="ok")

# === Healthcheck ===
async def healthcheck(request):
    return web.Response(text="OK")

# === Приложение ===
app = web.Application()
app.router.add_post(WEBHOOK_PATH, handle_webhook)
app.router.add_get("/healthz", healthcheck)

# === Startup ===
async def on_startup():
    await bot.set_webhook(WEBHOOK_URL)
    print(f"✅ Webhook установлен: {WEBHOOK_URL}")

    for token in SUPPORTED_TOKENS:
        scheduler.add_job(
            lambda t=token: send_email_with_attachment(
                "dancryptodan@gmail.com",
                f"Автоотчёт {t}",
                "Отчёт во вложении.",
                export_to_excel(t)
            ),
            trigger="cron",
            hour=9,
            minute=0
        )
    scheduler.start()

# === Запуск ===
if __name__ == "__main__":
    import asyncio

    async def main():
        await on_startup()
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", 8000)
        await site.start()
        print("🚀 Webhook сервер запущен на порту 8000")

        while True:
            await asyncio.sleep(3600)

    asyncio.run(main())
