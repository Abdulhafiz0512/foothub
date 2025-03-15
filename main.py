from telegram.ext import Application
from telegram.request import HTTPXRequest
from config import TOKEN
from database import init_db
from handlers import setup_handlers


def main():
    # Initialize database
    init_db()

    # Set up application with proper request adapter
    request = HTTPXRequest()
    application = Application.builder().token(TOKEN).request(request).build()

    # Set up all handlers
    setup_handlers(application)

    # Start polling
    application.run_polling()


if __name__ == '__main__':
    main()