from telegram import Update
from telegram.ext import ContextTypes


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a help message with available commands"""
    help_text = (
        "🍔 *Food Combo Bot Commands* 🍕\n\n"
        "/start - Start a new food combo submission\n"
        "/new - Alternative to start a new submission\n"
        "/nickname - Change your display nickname\n"
        "/cancel - Cancel the current submission process\n"
        "/help - Show this help message\n\n"
        "To submit a food combo:\n"
        "1. Start with /start or /new\n"
        "2. Provide your nickname (or use existing)\n"
        "3. Enter the number of food pictures\n"
        "4. Upload your food pictures\n"
        "5. Upload a payment screenshot as proof\n"
        "6. Enter number of people who ordered\n"
        "7. Select the delivery service\n"
        "8. Confirm your submission\n\n"
        "Your submission will be reviewed by admins before being published to the channel."
    )

    await update.message.reply_text(help_text, parse_mode='Markdown')