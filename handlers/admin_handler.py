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


pending_admin_additions = {}


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

    # Send instructions to the admin
    await update.message.reply_text(
        f"To add @{username} as an admin, ask them to:\n\n"
        f"1. Start the bot if they haven't already\n"
        f"2. Send /verifyadmin to the bot\n\n"
        f"Once they do this, you will receive a notification to confirm"
    )

    # Store this pending admin request
    pending_admin_additions[username.lower()] = {
        'requester_id': user_id,
        'status': 'pending'
    }


async def verify_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Command for users to verify their identity for admin addition"""
    user_id = update.effective_user.id
    username = update.effective_user.username

    if not username:
        await update.message.reply_text("You need to have a username set in Telegram to become an admin.")
        return

    username = username.lower()

    # Check if this user has a pending admin addition
    if username in pending_admin_additions and pending_admin_additions[username]['status'] == 'pending':
        requester_id = pending_admin_additions[username]['requester_id']

        # Send confirmation to the admin who requested this
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Confirm", callback_data=f"confirm_admin_{user_id}_{username}"),
                InlineKeyboardButton("Cancel", callback_data=f"cancel_admin_{user_id}_{username}")
            ]
        ])

        await context.bot.send_message(
            chat_id=requester_id,
            text=f"@{username} (ID: {user_id}) wants to be added as an admin. Confirm?",
            reply_markup=keyboard
        )

        # Notify the user
        await update.message.reply_text("Verification request sent to the admin. Please wait for confirmation.")

        # Update status
        pending_admin_additions[username]['status'] = 'verifying'
        pending_admin_additions[username]['user_id'] = user_id
    else:
        await update.message.reply_text("There is no pending admin verification request for your username.")


async def admin_confirmation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin confirmation callbacks"""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id

    # Check if the user is an admin
    if not await is_admin(user_id):
        await query.edit_message_text("You are not authorized to perform this action.")
        return

    action, user_id_to_add, username = query.data.split('_')[1:]
    user_id_to_add = int(user_id_to_add)

    if action == "confirm":
        # Get current admin IDs from .env
        admin_ids_str = os.getenv('ADMIN_IDS', '')
        admin_ids = [int(id.strip()) for id in admin_ids_str.split(',') if id.strip()]

        # Check if user is already an admin
        if user_id_to_add in admin_ids:
            await query.edit_message_text(f"User @{username} is already an admin.")
            return

        # Add new admin ID to the list
        admin_ids.append(user_id_to_add)

        # Update .env file with the new admin list
        new_admin_ids_str = ','.join(str(id) for id in admin_ids)
        dotenv_path = os.path.join(os.getcwd(), '.env')
        set_key(dotenv_path, 'ADMIN_IDS', new_admin_ids_str)

        # Reload environment variables
        load_dotenv()

        await query.edit_message_text(f"✅ Successfully added @{username} as an admin.")

        # Notify the new admin
        try:
            await context.bot.send_message(
                chat_id=user_id_to_add,
                text="✅ You have been added as an admin to the Food Combo submissions bot."
            )
        except Exception as e:
            logger.error(f"Error notifying new admin {user_id_to_add}: {e}")

        # Clean up pending addition
        if username.lower() in pending_admin_additions:
            del pending_admin_additions[username.lower()]

    elif action == "cancel":
        await query.edit_message_text(f"❌ Admin addition for @{username} has been cancelled.")

        # Notify the user
        try:
            await context.bot.send_message(
                chat_id=user_id_to_add,
                text="Your admin request has been denied."
            )
        except Exception as e:
            logger.error(f"Error notifying user {user_id_to_add}: {e}")

        # Clean up pending addition
        if username.lower() in pending_admin_additions:
            del pending_admin_additions[username.lower()]

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