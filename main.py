from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.session.aiohttp import AiohttpSession
from aiohttp import web
import logging
import os
import json

API_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"

storage = MemoryStorage()
session = AiohttpSession()
bot = Bot(token=API_TOKEN, session=session, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=storage)

DATA_FILE = "data.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"avg_price": 0, "eth_total": 0, "usdt_total": 0, "history": []}
    with open(DATA_FILE, 'r') as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

@dp.message(lambda message: message.text.startswith("/start"))
async def start_cmd(message: Message):
    await message.answer("Привет, Даниэль! Я твой бот по ETH на споте. Напиши /status, чтобы увидеть стратегию.")

@dp.message(lambda message: message.text.startswith("/status"))
async def status_cmd(message: Message):
    data = load_data()
    text = (
        f"<b>Средняя цена входа:</b> {data['avg_price']:.2f} USDT\n"
        f"<b>Всего ETH:</b> {data['eth_total']:.4f}\n"
        f"<b>Потрачено USDT:</b> {data['usdt_total']:.2f}"
    )
    await message.answer(text)

@dp.message(lambda message: message.text.startswith("/add"))
async def add_cmd(message: Message):
    try:
        parts = message.text.split()
        price = float(parts[1])
        amount = float(parts[2])

        data = load_data()
        total_usdt = data['usdt_total'] + price * amount
        total_eth = data['eth_total'] + amount
        avg_price = total_usdt / total_eth

        data['eth_total'] = total_eth
        data['usdt_total'] = total_usdt
        data['avg_price'] = avg_price
        data['history'].append({"action": "add", "price": price, "amount": amount})
        save_data(data)

        await message.answer(f"Добавлено {amount} ETH по {price} USDT\nНовая средняя: {avg_price:.2f} USDT")
    except:
        await message.answer("Формат: /add [цена] [кол-во ETH]")

@dp.message(lambda message: message.text.startswith("/fix"))
async def fix_cmd(message: Message):
    try:
        parts = message.text.split()
        price = float(parts[1])
        percent = float(parts[2])

        data = load_data()
        eth_to_sell = data['eth_total'] * (percent / 100)
        usdt_gained = eth_to_sell * price

        data['eth_total'] -= eth_to_sell
        data['usdt_total'] -= data['avg_price'] * eth_to_sell
        data['history'].append({"action": "fix", "price": price, "amount": eth_to_sell})
        save_data(data)

        await message.answer(f"Зафиксировано {eth_to_sell:.4f} ETH по {price} USDT\nПолучено: {usdt_gained:.2f} USDT")
    except:
        await message.answer("Формат: /fix [цена] [процент от позиции]")

@dp.message(lambda message: message.text.startswith("/avgprice"))
async def avg_cmd(message: Message):
    data = load_data()
    await message.answer(f"Текущая средняя цена: {data['avg_price']:.2f} USDT")

@dp.message(lambda message: message.text.startswith("/reset"))
async def reset_cmd(message: Message):
    save_data({"avg_price": 0, "eth_total": 0, "usdt_total": 0, "history": []})
    await message.answer("Данные сброшены. Можно начинать новую сессию.")

async def on_startup(app):
    await bot.set_webhook(WEBHOOK_URL)

async def on_shutdown(app):
    await bot.delete_webhook()
    await bot.session.close()

async def handle_webhook(request):
    body = await request.read()
    update = types.Update.model_validate_json(body.decode())
    await dp.feed_update(bot, update)
    return web.Response()

app = web.Application()
app.router.add_post(WEBHOOK_PATH, handle_webhook)
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
