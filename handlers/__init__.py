from telegram.ext import ConversationHandler, CommandHandler, CallbackQueryHandler

from .start_handler import start, change_nickname, cancel
from .submission_handler import (
    get_nickname, get_image_count, upload_images, upload_check,
    get_people_count, get_delivery_source, confirm_submission,
   submit_command
)
from .admin_handler import admin_action, delete_post, list_pending, add_admin
from .general_handler import help_command

from config import START, NICKNAME, IMAGE_COUNT, UPLOAD_IMAGES, UPLOAD_CHECK, PEOPLE_COUNT, DELIVERY_SOURCE, CONFIRM
from telegram.ext import MessageHandler, filters


def setup_handlers(application):
    """Set up all handlers for the application"""

    # Main conversation handler for submissions
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CommandHandler('new', start),
            CommandHandler('nickname', change_nickname),
            CommandHandler("submit", submit_command),
            CommandHandler('help', help_command)
        ],
        states={
            NICKNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_nickname)],
            IMAGE_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_image_count)],
            UPLOAD_IMAGES: [MessageHandler(filters.PHOTO, upload_images)],
            UPLOAD_CHECK: [MessageHandler(filters.PHOTO, upload_check)],
            PEOPLE_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_people_count)],
            DELIVERY_SOURCE: [CallbackQueryHandler(get_delivery_source, pattern=r'^source_')],
            CONFIRM: [CallbackQueryHandler(confirm_submission, pattern=r'^confirm_')]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )

    # Add all handlers
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CallbackQueryHandler(admin_action, pattern=r'^(approve|reject)_'))
    application.add_handler(CommandHandler("addadmin", add_admin))
    application.add_handler(CommandHandler('delete', delete_post))
    application.add_handler(CommandHandler('pending', list_pending))