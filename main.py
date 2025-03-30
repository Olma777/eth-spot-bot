import os
import smtplib
import openpyxl
import json
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import GetWebhookInfo
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio

# ========== Переменные окружения ==========
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))

API_TOKEN = os.getenv("BOT_TOKEN")

SUPPORTED_TOKENS = ["ETH", "DOT", "AVAX", "RENDER"]

# ========== Инициализация ==========
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

scheduler = AsyncIOScheduler()
scheduler.start()

# ========== FSM ==========
class EmailReport(StatesGroup):
    waiting_for_email = State()

selected_token = {}

# ========== Работа с данными ==========
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

# ========== Email ==========
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
    part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(file_path)}")
    msg.attach(part)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)

# ========== Команды ==========
@router.message(F.text == "/start")
async def start_handler(message: Message):
    await message.answer("Привет! Я бот-аналитик. Напиши /send_email, чтобы получить отчёт.")

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

@router.message(F.text.startswith("/webhook_info"))
async def webhook_info(message: Message):
    info = await bot(GetWebhookInfo())
    await message.answer(f"Webhook URL: {info.url}\nHas custom cert: {info.has_custom_certificate}\nPending updates: {info.pending_update_count}")

# ========== Автоотчёты ==========
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

# ========== Запуск Polling ==========
if __name__ == "__main__":
    async def main():
        print("🤖 Бот запущен в режиме polling")
        await dp.start_polling(bot)

    asyncio.run(main())
