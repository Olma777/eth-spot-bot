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
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
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

# Список поддерживаемых токенов
TOKENS = ["ETH", "DOT", "AVAX", "RENDER"]

# Состояния для FSM
class EmailState(StatesGroup):
    email = State()

# Функция для загрузки данных из JSON
def load_data(token):
    try:
        with open(f"{token}.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"Файл {token}.json не найден.")
        return []
    except json.JSONDecodeError:
        logging.error(f"Ошибка декодирования JSON в файле {token}.json.")
        return []

# Функция для сохранения данных в JSON
def save_data(token, data):
    try:
        with open(f"{token}.json", "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logging.error(f"Ошибка сохранения данных в файл {token}.json: {e}")

# Функция для генерации Excel-отчета
def generate_excel(token, data):
    wb = Workbook()
    ws = wb.active
    ws.append(["Дата", "Тип операции", "Цена", "Объем"])
    for item in data:
        ws.append([item["date"], item["type"], item["price"], item["amount"]])
    filename = f"{token}_report.xlsx"
    wb.save(filename)
    return filename

# Функция для отправки email
async def send_email(email, filename, token):
    msg = EmailMessage()
    msg["Subject"] = f"Отчет по {token}"
    msg["From"] = SMTP_USER
    msg["To"] = email
    with open(filename, "rb") as f:
        file_data = f.read()
        msg.add_attachment(file_data, maintype="application", subtype="xlsx", filename=filename)
    try:
        if SMTP_PORT == 587:
            with SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)
        else:
            with SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
                server.login(SMTP_USER, SMTP_PASS)
                server.send_message(msg)
        logging.info(f"Отчет {filename} отправлен на {email}")
        return True
    except Exception as e:
        logging.error(f"Ошибка отправки email: {e}")
        return False

# Обработчик команды /start
@router.message(CommandStart())
async def cmd_start(message: types.Message):
    logging.info(f"Получена команда /start от {message.from_user.id}")
    try:
        await message.answer("Привет! Выберите токен для работы:", reply_markup=get_token_keyboard())
    except Exception as e:
        logging.error(f"Ошибка при обработке /start от {message.from_user.id}: {e}")

# Обработчик выбора токена
@router.callback_query(F.data.in_(TOKENS))
async def process_token(callback: types.CallbackQuery, state: FSMContext):
    logging.info(f"Выбран токен {callback.data} от {callback.from_user.id}")
    try:
        await state.update_data(token=callback.data)
        await callback.message.answer(f"Выбран токен: {callback.data}. Что вы хотите сделать?", reply_markup=get_action_keyboard())
        await callback.answer()
    except Exception as e:
        logging.error(f"Ошибка при выборе токена {callback.data} от {callback.from_user.id}: {e}")

# Обработчик выбора действия (добавить сделку)
@router.callback_query(F.data == "add_trade")
async def add_trade(callback: types.CallbackQuery, state: FSMContext):
    logging.info(f"Выбрано действие 'добавить сделку' от {callback.from_user.id}")
    try:
        await callback.message.answer("Введите данные сделки в формате: тип (buy/sell), цена, объем.")
        await state.set_state("add_trade_data")
        await callback.answer()
    except Exception as e:
        logging.error(f"Ошибка при выборе действия 'добавить сделку' от {callback.from_user.id}: {e}")

# Обработчик ввода данных сделки
@router.message(F.text)
async def process_trade_data(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state == "add_trade_data":
        try:
            trade_type, price, amount = message.text.split(",")
            price, amount = float(price), float(amount)
            data = await state.get_data()
            token = data["token"]
            trades = load_data(token)
            trades.append({
                "date": datetime.now().isoformat(),
                "type": trade_type.strip().lower(),
                "price": price,
                "amount": amount
            })
            save_data(token, trades)
            logging.info(f"Сделка добавлена от {message.from_user.id}")
            await message.answer("Сделка добавлена.")
            await state.clear()
        except ValueError:
            logging.error(f"Неверный формат ввода данных сделки от {message.from_user.id}")
            await message.answer("Неверный формат. Попробуйте снова.")
        except Exception as e:
            logging.error(f"Ошибка при обработке данных сделки от {message.from_user.id}: {e}")
            await message.answer("Произошла ошибка, попробуйте позже.")
        await state.set_state(None)
    else:
        logging.warning(f"Попытка ввода данных сделки без выбора действия от {message.from_user.id}")
        await message.answer("Пожалуйста, сначала выберите операцию добавления сделки.")

# Обработчик выбора действия (получить отчет)
@router.callback_query(F.data == "get_report")
async def get_report(callback: types.CallbackQuery, state: FSMContext):
    logging.info(f"Выбрано действие 'получить отчет' от {callback.from_user.id}")
    try:
        await callback.message.answer("Введите ваш email для отправки отчета:")
        await state.set_state(EmailState.email)
        await callback.answer()
    except Exception as e:
        logging.error(f"Ошибка при выборе действия 'получить отчет' от {callback.from_user.id}: {e}")

# Обработчик ввода email
@router.message(F.text, EmailState.email)
async def process_email(message: types.Message, state: FSMContext):
    email = message.text
    if "@" in email:
        data = await state.get_data()
        token = data["token"]
        trades = load_data(token)
        filename = generate_excel(token, trades)
        try:
            if await send_email(email, filename, token):
                logging.info(f"Отчет отправлен на {email} от {message.from_user.id}")
                await message.answer("Отчет отправлен на ваш email.")
            else:
                logging.error(f"Ошибка при отправке отчета на {email} от {message.from_user.id}")
                await message.answer("Ошибка при отправке отчета.")
        except Exception as e:
            logging.error(f"Ошибка при обработке email от {message.from_user.id}: {e}")
            await message.answer("Произошла ошибка, попробуйте позже.")
        os.remove(filename)
        await state.clear()
    else:
        logging.error(f"Неверный формат email от {message.from_user.id}")
        await message.answer("Неверный формат email. Попробуйте снова.")
        await state.set_state(EmailState.email)

# Клавиатуры
def get_token_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=token, callback_data=token)] for token in TOKENS])
    return keyboard

def get_action_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Добавить сделку", callback_data="add_trade")],
        [InlineKeyboardButton(text="Получить отчет", callback_data="get_report")]
    ])
    return keyboard

# Healthcheck
async def healthcheck(request):
    return web.Response(text="OK")

# Webhook
async def on_startup(bot: Bot):
    webhook_url = f"{WEBHOOK_HOST}/webhook"
    await bot.set_webhook(webhook_url)

async def handle_root(request):
    return web.Response(text="Bot is running")

async function main():
    app = web.Application()
    webhook_requests_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_requests_handler.register(app, path="/webhook")
    setup_application(app, dp, bot=bot)
    app.router.add_get("/healthz", healthcheck)
    app.router.add_get("/", handle_root)
    dp.startup.register(on_startup)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 8080)))
    await site.start()
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
