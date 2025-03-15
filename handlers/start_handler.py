from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ContextTypes, ConversationHandler
from database import Session
from models import User
from config import NICKNAME, IMAGE_COUNT


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the conversation and handle user registration"""
    user = update.effective_user

    # Check if user exists in database
    session = Session()
    existing_user = session.query(User).filter_by(user_id=user.id).first()

    if not existing_user:
        # New user - create record and ask for nickname
        new_user = User(user_id=user.id)
        session.add(new_user)
        session.commit()
        session.close()

        await update.message.reply_text(
            f"Welcome to the Food Combo Channel Bot! 🍔🍕\n\n"
            f"This bot helps you submit your favorite food combinations to our channel.\n\n"
            f"To get started, please provide a nickname that will be used for your posts."
        )
        return NICKNAME
    else:
        # Returning user - check if they have a nickname
        nickname = existing_user.nickname
        session.close()

        if nickname:
            # User already has a nickname - store it in context and skip to next step
            context.user_data['nickname'] = nickname

            await update.message.reply_text(
                f"Welcome back, {nickname}! 👋\n\n"
                f"Let's submit your food combo. How many food images do you want to upload? (1-10)",
                reply_markup=ReplyKeyboardRemove()
            )
            return IMAGE_COUNT
        else:
            # User exists but doesn't have a nickname yet
            await update.message.reply_text(
                f"Welcome to the Food Combo Channel Bot! 🍔🍕\n\n"
                f"Please provide a nickname that will be used for your posts."
            )
            return NICKNAME


async def change_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle nickname change request"""
    await update.message.reply_text(
        "Please enter your new nickname that will be used for your posts."
    )
    return NICKNAME

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel the current conversation"""
    await update.message.reply_text("Operation cancelled. Type /start to begin again.")
    return ConversationHandler.END