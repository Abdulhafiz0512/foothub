from telegram import Update, InputMediaPhoto, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes
from database import Session
from models import Submission, Image
from utils import is_admin
from config import CHANNEL_ID, logger


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
            f"Food Combo by: {submission.nickname}\n"
            f"Number of People: {submission.people_count}\n"
            f"Delivery Source: {submission.delivery_source}"
        )

        # Prepare media group with all images
        media_group = []

        # Add first food image with caption
        if food_images:
            media_group.append(InputMediaPhoto(
                media=food_images[0].file_id,
                caption=caption
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

        await query.message.reply_text(f"Submission {submission_id} approved and published.")

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

        await query.message.reply_text(f"Submission {submission_id} rejected.")

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