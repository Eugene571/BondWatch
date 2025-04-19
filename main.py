import logging
from telegram.ext import Application
from telegram.ext import ContextTypes
from config import TELEGRAM_TOKEN
from bot.handlers import register_handlers
from bot.database import init_db
from apscheduler.schedulers.background import BackgroundScheduler
from bot.notifications import check_and_notify

# Настройка логгирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG,
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()  # вывод в консоль
    ]
)


# Обработчик ошибок
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logging.error("Exception while handling update:", exc_info=context.error)


# Основная точка входа
def main():
    logging.info("Initializing database...")
    init_db()

    logging.info("Starting bot...")
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    register_handlers(app)
    app.add_error_handler(error_handler)

    # Настройка APScheduler с использованием job queue
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_and_notify, 'interval', seconds=30, args=[app.bot])
    scheduler.start()

    logging.info("Bot started...")
    app.run_polling()  # теперь без asyncio.run()


if __name__ == "__main__":
    main()
