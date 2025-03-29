import os
import smtplib
import openpyxl
import json
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from aiogram.fsm.storage.memory import MemoryStorage

# SMTP-переменные через Render Environment
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = "oxeygawgsbcrpfae"  # 16-значный App Password
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))

SUPPORTED_TOKENS = ["ETH", "DOT", "AVAX", "RENDER"]

# Базовые настройки бота
API_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Healthcheck endpoint
async def healthcheck(request):
    return web.Response(text="OK")

app = web.Application()
app.router.add_get("/healthz", healthcheck)

# Загрузка и сохранение истории

def load_data(token):
    try:
        with open(f"{token}.json", "r") as f:
            return json.load(f)
    except:
        return {"avg_price": 0, "eth_total": 0, "usdt_total": 0, "history": []}

def save_data(token, data):
    with open(f"{token}.json", "w") as f:
        json.dump(data, f, indent=2)

# Email-функция
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

# Команда отправки email
@dp.message(F.text.startswith("/send_email"))
async def send_email_cmd(message: Message):
    try:
        parts = message.text.strip().split()
        if len(parts) < 3:
            await message.answer("Формат: /send_email TOKEN EMAIL")
            return

        token = parts[1].upper()
        email = parts[2]

        if token not in SUPPORTED_TOKENS:
            await message.answer("Неподдерживаемый токен. Доступны: ETH, DOT, AVAX, RENDER")
            return

        data = load_data(token)
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = f"{token}_history"
        ws.append(["Дата", "Тип", "Цена", "Кол-во"])
        for entry in data['history']:
            ws.append([entry.get("time", "-"), entry['action'], entry['price'], entry['amount']])
        filename = f"{token}_history.xlsx"
        wb.save(filename)

        await send_email_with_attachment(
            to_email=email,
            subject=f"История {token} — {datetime.now().strftime('%Y-%m-%d')}",
            body="Автоотчёт от твоего трейдинг-бота.",
            file_path=filename
        )
        await message.answer(f"📧 Отчёт по {token} отправлен на {email}!")
    except Exception as e:
        await message.answer(f"Ошибка при отправке email: {e}")

# Запуск aiohttp + Webhook
if __name__ == '__main__':
    import asyncio

    async def on_startup(dispatcher: Dispatcher, bot: Bot):
        await bot.set_webhook(WEBHOOK_URL)

    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot, on_startup=on_startup)

    web.run_app(app, host="0.0.0.0", port=8000)
