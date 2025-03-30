from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

async def on_startup(app):
    await bot.set_webhook(WEBHOOK_URL)

    for token in SUPPORTED_TOKENS:
        scheduler.add_job(
            lambda t=token: send_email_with_attachment(
                "dancryptodan@gmail.com",
                f"Утренний отчёт {t}",
                "Ваш отчёт во вложении.",
                export_to_excel(t)
            ),
            trigger="cron",
            hour=9,
            minute=0
        )
    scheduler.start()

async def main():
    app = web.Application()
    app.router.add_post(WEBHOOK_PATH, handle_webhook)
    app.router.add_get("/healthz", healthcheck)

    # Привязываем webhook dispatcher к приложению
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    app.on_startup.append(on_startup)
    setup_application(app, dp)

    return app

if __name__ == "__main__":
    web.run_app(main(), host="0.0.0.0", port=8000)
