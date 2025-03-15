import uuid
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from config import IMAGE_COUNT, UPLOAD_IMAGES, UPLOAD_CHECK, PEOPLE_COUNT, DELIVERY_SOURCE, CONFIRM, ADMIN_IDS, NICKNAME
from database import Session
from models import User, Submission, Image


async def clear_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete all previous messages from the conversation."""
    # Get the correct chat ID and bot
    if hasattr(update, 'callback_query') and update.callback_query:
        # For callback queries
        chat_id = update.callback_query.message.chat_id
        bot = context.bot  # Use context.bot instead of message.bot
    else:
        # For regular updates
        chat_id = update.effective_chat.id
        bot = context.bot  # Use context.bot instead of message.bot

    for msg_id in context.user_data.get('messages', []):
        try:
            await bot.delete_message(
                chat_id=chat_id, message_id=msg_id
            )
        except Exception as e:
            print(f"Error deleting message {msg_id}: {e}")  # Add logging for debugging
            pass  # Ignore errors if message is already deleted

    context.user_data['messages'] = []  # Reset message storage


async def submit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /submit command to start a new submission with existing nickname"""
    user_id = update.effective_user.id

    # Check if user has a nickname saved
    session = Session()
    user = session.query(User).filter_by(user_id=user_id).first()

    if user and user.nickname:
        # User exists and has a nickname
        context.user_data['nickname'] = user.nickname

        msg = await update.message.reply_text(
            f"Starting new submission as {user.nickname}! How many food images do you want to upload? (1-10)"
        )
        context.user_data.setdefault('messages', []).append(msg.message_id)

        session.close()
        return IMAGE_COUNT
    else:
        # User doesn't exist or doesn't have a nickname
        msg = await update.message.reply_text(
            "Please provide a nickname (up to 30 characters):"
        )
        context.user_data.setdefault('messages', []).append(msg.message_id)

        session.close()
        return NICKNAME


async def get_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get or update user's nickname"""
    nickname = update.message.text.strip()

    if len(nickname) > 30:
        msg = await update.message.reply_text(
            "Nickname is too long. Please provide a nickname with 30 characters or less."
        )
        context.user_data.setdefault('messages', []).append(msg.message_id)
        return NICKNAME

    context.user_data['nickname'] = nickname

    session = Session()
    user = session.query(User).filter_by(user_id=update.effective_user.id).first()

    if user:
        user.nickname = nickname
        session.commit()

    session.close()

    msg = await update.message.reply_text(
        f"Thanks, {nickname}! How many food images do you want to upload? (1-10)"
    )
    context.user_data.setdefault('messages', []).append(msg.message_id)

    return IMAGE_COUNT


async def get_image_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        image_count = int(update.message.text)
        if image_count <= 0:
            msg = await update.message.reply_text("Please enter a positive number.")
            context.user_data.setdefault('messages', []).append(msg.message_id)
            return IMAGE_COUNT

        context.user_data['image_count'] = image_count
        context.user_data['images'] = []
        context.user_data['current_image'] = 1

        msg = await update.message.reply_text(
            f"Please upload image 1 of {image_count} for your food combo."
        )
        context.user_data.setdefault('messages', []).append(msg.message_id)

        return UPLOAD_IMAGES

    except ValueError:
        msg = await update.message.reply_text("Please enter a valid number.")
        context.user_data.setdefault('messages', []).append(msg.message_id)
        return IMAGE_COUNT


async def upload_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        context.user_data['images'].append(file_id)

        current = context.user_data['current_image']
        total = context.user_data['image_count']

        if current < total:
            context.user_data['current_image'] += 1
            msg = await update.message.reply_text(
                f"Please upload image {current + 1} of {total} for your food combo."
            )
            context.user_data.setdefault('messages', []).append(msg.message_id)
            return UPLOAD_IMAGES
        else:
            msg = await update.message.reply_text(
                "Now, please upload a check photo of your order."
            )
            context.user_data.setdefault('messages', []).append(msg.message_id)
            return UPLOAD_CHECK
    else:
        msg = await update.message.reply_text("Please upload an image.")
        context.user_data.setdefault('messages', []).append(msg.message_id)
        return UPLOAD_IMAGES


async def upload_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        context.user_data['check_image'] = file_id

        msg = await update.message.reply_text(
            "How many people ordered this food combo?"
        )
        context.user_data.setdefault('messages', []).append(msg.message_id)

        return PEOPLE_COUNT
    else:
        msg = await update.message.reply_text("Please upload a check image.")
        context.user_data.setdefault('messages', []).append(msg.message_id)
        return UPLOAD_CHECK


async def get_people_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        people_count = int(update.message.text)
        if people_count <= 0:
            msg = await update.message.reply_text("Please enter a positive number.")
            context.user_data.setdefault('messages', []).append(msg.message_id)
            return PEOPLE_COUNT

        context.user_data['people_count'] = people_count

        keyboard = [
            [
                InlineKeyboardButton("Wolt", callback_data="source_wolt"),
                InlineKeyboardButton("Yandex Eats", callback_data="source_yandex"),
                InlineKeyboardButton("Uzum Tezkor", callback_data="source_uzum")
            ]
        ]

        msg = await update.message.reply_text(
            "Please select the delivery source:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        context.user_data.setdefault('messages', []).append(msg.message_id)

        return DELIVERY_SOURCE

    except ValueError:
        msg = await update.message.reply_text("Please enter a valid number.")
        context.user_data.setdefault('messages', []).append(msg.message_id)
        return PEOPLE_COUNT


async def get_delivery_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    source = query.data.replace("source_", "")
    context.user_data['delivery_source'] = source.capitalize()

    # Clear chat before sending preview
    await clear_chat(update, context)

    # Send a preview post to the user before confirmation
    nickname = context.user_data['nickname']
    people_count = context.user_data['people_count']
    delivery_source = context.user_data['delivery_source']
    image_count = context.user_data['image_count']

    preview_text = (
        f"📢 <b>Submission Preview</b> 📢\n\n"
        f"👤 <b>Nickname:</b> {nickname}\n"
        f"📸 <b>Number of Images:</b> {image_count}\n"
        f"👥 <b>People Count:</b> {people_count}\n"
        f"🚚 <b>Delivery Source:</b> {delivery_source}\n\n"
        f"✅ <b>If everything is correct, please confirm below:</b>"
    )

    preview_msg = await query.message.reply_text(preview_text, parse_mode="HTML")
    context.user_data.setdefault('messages', []).append(preview_msg.message_id)

    # Send images
    for file_id in context.user_data['images']:
        image_msg = await query.message.reply_photo(photo=file_id)
        context.user_data.setdefault('messages', []).append(image_msg.message_id)

    # Send check image
    check_msg = await query.message.reply_photo(
        photo=context.user_data['check_image'],
        caption="🧾 <b>Check Image</b>",
        parse_mode="HTML"
    )
    context.user_data.setdefault('messages', []).append(check_msg.message_id)

    # Confirmation buttons
    confirm_msg = await query.message.reply_text(
        "Would you like to submit this post?",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Yes, Submit", callback_data="confirm_yes"),
                InlineKeyboardButton("❌ No, Cancel", callback_data="confirm_no")
            ]
        ])
    )
    context.user_data.setdefault('messages', []).append(confirm_msg.message_id)

    return CONFIRM


async def confirm_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "confirm_no":
        msg = await query.message.reply_text("Submission cancelled. Type /submit to begin again.")
        context.user_data.setdefault('messages', []).append(msg.message_id)
        return ConversationHandler.END

    # Generate unique submission ID
    submission_id = str(uuid.uuid4())
    context.user_data['submission_id'] = submission_id

    # Save submission to database
    session = Session()

    new_submission = Submission(
        submission_id=submission_id,
        user_id=update.effective_user.id,
        nickname=context.user_data['nickname'],
        image_count=context.user_data['image_count'],
        people_count=context.user_data['people_count'],
        delivery_source=context.user_data['delivery_source']
    )

    session.add(new_submission)
    session.commit()

    # Save images
    for i, file_id in enumerate(context.user_data['images']):
        image = Image(
            submission_id=submission_id,
            file_id=file_id,
            is_check_image=False,
            sequence=i + 1
        )
        session.add(image)

    # Save check image
    check_image = Image(
        submission_id=submission_id,
        file_id=context.user_data['check_image'],
        is_check_image=True
    )
    session.add(check_image)

    session.commit()
    session.close()
    print(f"Messages to delete: {context.user_data.get('messages', [])}")
    # Clear all previous messages from the chat
    await clear_chat(update, context)

    # Save the important data before clearing user_data
    saved_nickname = context.user_data.get('nickname')
    saved_images = context.user_data.get('images', [])
    saved_check_image = context.user_data.get('check_image')
    saved_people_count = context.user_data.get('people_count')
    saved_delivery_source = context.user_data.get('delivery_source')

    # Clear user data but keep nickname for future submissions
    context.user_data.clear()
    context.user_data['nickname'] = saved_nickname
    context.user_data['messages'] = []  # Reset message tracking

    # Send thank you message and track it
    thank_you_msg = await query.message.reply_text(
        "Thank you! Your submission has been received and is pending admin approval. "
        "You'll be notified when it's approved or rejected.\n\n"
    )
    context.user_data['messages'].append(thank_you_msg.message_id)

    # Notify admins
    for admin_id in ADMIN_IDS:
        # First, send submission details
        await context.bot.send_message(
            chat_id=admin_id,
            text=f"New submission received (ID: {submission_id}):\n\n"
                 f"👤 Nickname: {saved_nickname}\n"
                 f"👥 Number of People: {saved_people_count}\n"
                 f"🚚 Delivery Source: {saved_delivery_source}"
        )

        # Send food images with caption for each image
        for i, file_id in enumerate(saved_images):
            caption = f"Food Image {i + 1}/{len(saved_images)}"
            await context.bot.send_photo(
                chat_id=admin_id,
                photo=file_id,
                caption=caption
            )

        # Send check image
        if saved_check_image:
            await context.bot.send_photo(
                chat_id=admin_id,
                photo=saved_check_image,
                caption="🧾 Check image"
            )

        # Send approval buttons
        await context.bot.send_message(
            chat_id=admin_id,
            text=f"Do you approve this submission (ID: {submission_id})?",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Approve", callback_data=f"approve_{submission_id}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"reject_{submission_id}")
                ]
            ])
        )
    return ConversationHandler.END


