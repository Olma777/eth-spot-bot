import os
import smtplib
import openpyxl
import json
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from datetime import datetime
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import GetWebhookInfo
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# 🛠️ Конфигурация из переменных окружения
SMTP_USER = os.getenv("SMTP_USER")  # dancryptodan@gmail.com
SMTP_PASS = os.getenv("SMTP_PASS")  # app password
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
API_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

SUPPORTED_TOKENS = ["ETH", "DOT", "AVAX", "RENDER"]

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

scheduler = AsyncIOScheduler()
scheduler.start()

# 📦 Состояние FSM
class EmailReport(StatesGroup):
    waiting_for_email = State()

selected_token = {}

# ✅ Healthcheck endpoint
async def healthcheck(request):
    return web.Response(text="OK")

app = web.Application()
app.router.add_get("/healthz", healthcheck)

# 📊 Загрузка и сохранение данных
def load_data(token):
    try:
        with open(f"{token}.json", "r") as f:
            return json.load(f)
    except:
        return {"avg_price": 0, "eth_total": 0, "usdt_total": 0, "history": []}

def save_data(token, data):
    with open(f"{token}.json", "w") as f:
        json.dump(data, f, indent=2)

def export_to_excel(token):
    data = load_data(token)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f"{token}_history"
    ws.append(["Дата", "Тип", "Цена", "Кол-во"])
    for entry in data['history']:
        ws.append([entry.get("time", "-"), entry['action'], entry['price'], entry['amount']])
    filename = f"{token}_history.xlsx"
    wb.save(filename)
    return filename

# 📧 Отправка email
async def send_email_with_attachment(to_email, subject, body, file_path):
    msg = MIMEMultipart()
    msg['From'] = SMTP_USER
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    part = MIMEBase('application', 'octet-stream')
    with open(file_path, 'rb') as f:
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', f'attachment; filename={os.path.basename(file_path)}')
    msg.attach(part)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)

# 🔘 Команды и колбэки
@router.message(F.text == "/send_email")
async def choose_token(message: Message, state: FSMContext):
    buttons = [[InlineKeyboardButton(text=t, callback_data=f"send:{t}")] for t in SUPPORTED_TOKENS]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Выбери токен для отправки отчёта:", reply_markup=keyboard)

@router.callback_query(F.data.startswith("send:"))
async def token_selected(callback_query, state: FSMContext):
    token = callback_query.data.split(":")[1]
    selected_token[callback_query.from_user.id] = token
    await callback_query.message.answer("Введите email, на который отправить отчёт:")
    await state.set_state(EmailReport.waiting_for_email)

@router.message(EmailReport.waiting_for_email)
async def process_email(message: Message, state: FSMContext):
    email = message.text.strip()
    user_id = message.from_user.id
    token = selected_token.get(user_id)
    file_path = export_to_excel(token)
    try:
        await send_email_with_attachment(
            to_email=email,
            subject=f"Отчёт по {token}",
            body="Ваш отчёт прилагается во вложении.",
            file_path=file_path
        )
        await message.answer(f"📧 Отчёт по {token} отправлен на {email}!")
    except Exception as e:
        await message.answer(f"❌ Ошибка при отправке: {e}")
    await state.clear()

# 📡 Информация о вебхуке
@router.message(F.text.startswith("/webhook_info"))
async def webhook_info(message: Message):
    info = await bot(GetWebhookInfo())
    await message.answer(
        f"Webhook URL: {info.url or 'не установлен'}\n"
        f"Has custom cert: {info.has_custom_certificate}\n"
        f"Pending updates: {info.pending_update_count}"
    )

# ⏰ Автоматическая отправка отчётов
for token in SUPPORTED_TOKENS:
    scheduler.add_job(
        lambda t=token: send_email_with_attachment(
            to_email="dancryptodan@gmail.com",
            subject=f"Утренний отчёт {t}",
            body="Ваш запланированный отчёт прилагается во вложении.",
            file_path=export_to_excel(t)
        ),
        trigger='cron', hour=9, minute=0
    )

# 🚀 Запуск
if __name__ == '__main__':
    import asyncio

    async def on_startup(dispatcher: Dispatcher, bot: Bot):
        await bot.set_webhook(WEBHOOK_URL)

    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot, on_startup=on_startup)
    web.run_app(app, host="0.0.0.0", port=8000)
