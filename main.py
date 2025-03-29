import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders

# SMTP-переменные через Render Environment
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))

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

@dp.message(lambda message: message.text.startswith("/send_email"))
async def send_email_cmd(message: Message):
    try:
        parts = message.text.strip().split()
        token = parts[1].upper()
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
            to_email="cryptodancing@proton.me",
            subject=f"История {token} — {datetime.now().strftime('%Y-%m-%d')}",
            body="Автоотчёт от твоего трейдинг-бота.",
            file_path=filename
        )
        await message.answer(f"📧 Отчёт по {token} отправлен на почту!")
    except Exception as e:
        await message.answer("Ошибка при отправке email. Проверь конфигурацию.")
