from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler
from database import Session
from models import User
from config import NICKNAME


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the conversation and handle user registration"""
    user = update.effective_user

    # Check if user exists in database
    session = Session()
    existing_user = session.query(User).filter_by(user_id=user.id).first()

    if not existing_user:
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