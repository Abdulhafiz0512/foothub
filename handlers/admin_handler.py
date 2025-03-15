from dotenv import set_key, load_dotenv
from telegram import Update, InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from database import Session
from models import Submission, Image
import os
from utils import is_admin
from config import CHANNEL_ID, logger

load_dotenv()
async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin approval/rejection of submissions"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    if not await is_admin(user_id):
        return

    action, submission_id = query.data.split('_', 1)

    session = Session()
    submission = session.query(Submission).filter_by(submission_id=submission_id).first()

    if not submission:
        await query.message.reply_text("Submission not found.")
        session.close()
        return

    submitter_id = submission.user_id

    if action == "approve":
        # Update status in database
        submission.status = "approved"

        # Get all images - both food and check images
        food_images = session.query(Image).filter_by(
            submission_id=submission_id,
            is_check_image=False
        ).order_by(Image.sequence).all()

        check_image = session.query(Image).filter_by(
            submission_id=submission_id,
            is_check_image=True
        ).first()

        # Create caption for the post
        caption = (
            "🍽️ <b>Food Combo Submission</b> 🚀\n\n"
            f"👤 <b>Nickname:</b> {submission.nickname}\n"
            f"📍 <b>Delivery From:</b> {submission.delivery_source}\n"
            f"👥 <b>Serves:</b> {submission.people_count}\n"
            f"🔥 <b>Why It’s a Great Deal:</b> { 'No description provided'}\n\n"
            "📸 <b>Check out my food combo!</b> 😍\n\n"
            "<b>Send your combo from @wwoffers_bot</b>"
        )

        # Prepare media group with all images
        media_group = []

        # Add first food image with caption
        if food_images:
            media_group.append(InputMediaPhoto(
                media=food_images[0].file_id,
                caption=caption,
                parse_mode="HTML"
            ))

            # Add remaining food images without caption
            for img in food_images[1:]:
                media_group.append(InputMediaPhoto(media=img.file_id))

        # Add check/payment image
        if check_image:
            media_group.append(InputMediaPhoto(media=check_image.file_id))

        # Send all images as a single media group
        if media_group:
            messages = await context.bot.send_media_group(
                chat_id=CHANNEL_ID,
                media=media_group
            )

            # Save the first message ID for reference
            if messages:
                submission.channel_post_id = messages[0].message_id

        session.commit()

        # Notify user
        try:
            await context.bot.send_message(
                chat_id=submitter_id,
                text="Your food combo submission has been approved and published to the channel!"
            )
        except Exception as e:
            logger.error(f"Error notifying user {submitter_id}: {e}")

        # Update the original message with confirmation
        new_text = f"✅ Submission {submission_id} approved and published to the channel.\n\n"
        new_text += f"Nickname: {submission.nickname}\n"
        new_text += f"People: {submission.people_count}\n"
        new_text += f"Source: {submission.delivery_source}"

        await query.message.edit_text(new_text)

    elif action == "reject":
        # Update status in database
        submission.status = "rejected"
        session.commit()

        # Notify user
        try:
            await context.bot.send_message(
                chat_id=submitter_id,
                text="Your food combo submission was not approved."
            )
        except Exception as e:
            logger.error(f"Error notifying user {submitter_id}: {e}")

        # Update the original message with confirmation
        new_text = f"❌ Submission {submission_id} rejected.\n\n"
        new_text += f"Nickname: {submission.nickname}\n"
        new_text += f"People: {submission.people_count}\n"
        new_text += f"Source: {submission.delivery_source}"

        await query.message.edit_text(new_text)

    session.close()
async def delete_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to delete a published post"""
    user_id = update.effective_user.id
    if not await is_admin(user_id):
        await update.message.reply_text("This command is only available to admins.")
        return

    if not context.args or len(context.args) != 1:
        await update.message.reply_text("Usage: /delete [submission_id]")
        return

    submission_id = context.args[0]

    session = Session()
    submission = session.query(Submission).filter_by(submission_id=submission_id).first()

    if not submission or submission.status != "approved" or not submission.channel_post_id:
        await update.message.reply_text("No published post found with that ID.")
        session.close()
        return

    # Delete from channel
    try:
        await context.bot.delete_message(
            chat_id=CHANNEL_ID,
            message_id=submission.channel_post_id
        )

        # Update status in database
        submission.status = "deleted"
        submission.channel_post_id = None
        session.commit()

        await update.message.reply_text(f"Post with ID {submission_id} has been deleted from the channel.")
    except Exception as e:
        await update.message.reply_text(f"Error deleting post: {e}")
    finally:
        session.close()


async def add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to add a new admin by username"""
    user_id = update.effective_user.id

    # Check if the user executing this command is an admin
    if not await is_admin(user_id):
        await update.message.reply_text("This command is only available to admins.")
        return

    # Check if command has the correct arguments
    if not context.args or len(context.args) != 1:
        await update.message.reply_text("Usage: /addadmin [username]")
        return

    username = context.args[0]
    # Remove @ symbol if included
    if username.startswith('@'):
        username = username[1:]

    # Try to get user info from username
    try:
        # Get user info from Telegram
        user = await context.bot.get_chat(f"@{username}")
        new_admin_id = user.id

        # Get current admin IDs from .env
        admin_ids_str = os.getenv('ADMIN_IDS', '')
        admin_ids = [int(id.strip()) for id in admin_ids_str.split(',') if id.strip()]

        # Check if user is already an admin
        if new_admin_id in admin_ids:
            await update.message.reply_text(f"User @{username} is already an admin.")
            return

        # Add new admin ID to the list
        admin_ids.append(new_admin_id)

        # Update .env file with the new admin list
        new_admin_ids_str = ','.join(str(id) for id in admin_ids)
        dotenv_path = os.path.join(os.getcwd(), '.env')
        set_key(dotenv_path, 'ADMIN_IDS', new_admin_ids_str)

        # Reload environment variables
        load_dotenv()

        await update.message.reply_text(
            f"✅ Successfully added @{username} as an admin.\nAdmin ID {new_admin_id} added to .env file.")

        # Notify the new admin
        try:
            await context.bot.send_message(
                chat_id=new_admin_id,
                text="You have been added as an admin to the Food Combo submissions bot."
            )
        except Exception as e:
            logger.error(f"Error notifying new admin {new_admin_id}: {e}")
            await update.message.reply_text(f"Admin added, but couldn't notify them: {e}")

    except Exception as e:
        await update.message.reply_text(
            f"Error adding admin: {e}\nMake sure the username is correct and the user has interacted with the bot at least once.")
        logger.error(f"Error adding admin with username {username}: {e}")
async def list_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to list pending submissions"""
    user_id = update.effective_user.id
    if not await is_admin(user_id):
        await update.message.reply_text("This command is only available to admins.")
        return

    session = Session()
    pending = session.query(Submission).filter_by(status="pending").all()

    if not pending:
        await update.message.reply_text("No pending submissions.")
        session.close()
        return

    message = "Pending submissions:\n\n"
    for sub in pending:
        message += f"ID: {sub.submission_id}\n"
        message += f"Nickname: {sub.nickname}\n"
        message += f"Created: {sub.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"

    await update.message.reply_text(message)
    session.close()