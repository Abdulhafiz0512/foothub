import uuid

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from config import IMAGE_COUNT, UPLOAD_IMAGES, UPLOAD_CHECK, PEOPLE_COUNT, DELIVERY_SOURCE, CONFIRM, ADMIN_IDS
from database import Session
from models import User, Submission, Image


async def get_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nickname = update.message.text

    # Save nickname to database
    session = Session()
    user = session.query(User).filter_by(user_id=update.effective_user.id).first()
    user.nickname = nickname
    session.commit()
    session.close()

    # Save nickname to context for this conversation
    context.user_data['nickname'] = nickname

    await update.message.reply_text(
        f"Great! Your nickname is set to '{nickname}'.\n\n"
        f"Now, let's submit your food combo. How many pictures do you have of your food combo? (e.g., '3')"
    )

    return IMAGE_COUNT

async def get_image_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        image_count = int(update.message.text)
        if image_count <= 0:
            await update.message.reply_text("Please enter a positive number.")
            return IMAGE_COUNT

        context.user_data['image_count'] = image_count
        context.user_data['images'] = []
        context.user_data['current_image'] = 1

        await update.message.reply_text(
            f"Please upload image 1 of {image_count} for your food combo."
        )

        return UPLOAD_IMAGES

    except ValueError:
        await update.message.reply_text("Please enter a valid number.")
        return IMAGE_COUNT

async def upload_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        context.user_data['images'].append(file_id)

        current = context.user_data['current_image']
        total = context.user_data['image_count']

        if current < total:
            context.user_data['current_image'] += 1
            await update.message.reply_text(
                f"Please upload image {current + 1} of {total} for your food combo."
            )
            return UPLOAD_IMAGES
        else:
            await update.message.reply_text(
                "Now, please upload a check photo of your order."
            )
            return UPLOAD_CHECK
    else:
        await update.message.reply_text("Please upload an image.")
        return UPLOAD_IMAGES

async def upload_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        context.user_data['check_image'] = file_id

        await update.message.reply_text(
            "How many people ordered this food combo?"
        )

        return PEOPLE_COUNT
    else:
        await update.message.reply_text("Please upload a check image.")
        return UPLOAD_CHECK

async def get_people_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        people_count = int(update.message.text)
        if people_count <= 0:
            await update.message.reply_text("Please enter a positive number.")
            return PEOPLE_COUNT

        context.user_data['people_count'] = people_count

        keyboard = [
            [
                InlineKeyboardButton("Wolt", callback_data="source_wolt"),
                InlineKeyboardButton("Yandex Eats", callback_data="source_yandex"),
                InlineKeyboardButton("Uzum Tezkor", callback_data="source_uzum")
            ]
        ]

        await update.message.reply_text(
            "Please select the delivery source:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return DELIVERY_SOURCE

    except ValueError:
        await update.message.reply_text("Please enter a valid number.")
        return PEOPLE_COUNT

async def get_delivery_source(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    source = query.data.replace("source_", "")
    context.user_data['delivery_source'] = source.capitalize()

    # Create summary message
    nickname = context.user_data['nickname']
    people_count = context.user_data['people_count']
    delivery_source = context.user_data['delivery_source']

    await query.message.reply_text(
        f"Please review your submission:\n\n"
        f"Nickname: {nickname}\n"
        f"Number of Images: {context.user_data['image_count']}\n"
        f"Number of People: {people_count}\n"
        f"Delivery Source: {delivery_source}\n\n"
        f"Would you like to submit this post?",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Yes, Submit", callback_data="confirm_yes"),
                InlineKeyboardButton("No, Cancel", callback_data="confirm_no")
            ]
        ])
    )

    return CONFIRM

async def confirm_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "confirm_no":
        await query.message.reply_text("Submission cancelled. Type /start to begin again.")
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
            sequence=i+1
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

    # Clear user data but keep nickname for future submissions
    saved_nickname = context.user_data.get('nickname')
    context.user_data.clear()
    context.user_data['nickname'] = saved_nickname

    await query.message.reply_text(
        "Thank you! Your submission has been received and is pending admin approval. "
        "You'll be notified when it's approved or rejected.\n\n"
        "Would you like to submit another food combo?",
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Yes, Submit Another", callback_data="submit_another"),
                InlineKeyboardButton("No, That's All", callback_data="no_more_submissions")
            ]
        ])
    )

    # Notify admins
    for admin_id in ADMIN_IDS:
        await context.bot.send_message(
            chat_id=admin_id,
            text=f"New submission received (ID: {submission_id}):\n\n"
                 f"Nickname: {saved_nickname}\n"
                 f"Number of People: {context.user_data.get('people_count', 'N/A')}\n"
                 f"Delivery Source: {context.user_data.get('delivery_source', 'N/A')}"
        )

        # Send food images
        for file_id in context.user_data.get('images', []):
            await context.bot.send_photo(chat_id=admin_id, photo=file_id)

        # Send check image
        if 'check_image' in context.user_data:
            await context.bot.send_photo(
                chat_id=admin_id,
                photo=context.user_data['check_image'],
                caption="Check image"
            )

        # Send approval buttons
        await context.bot.send_message(
            chat_id=admin_id,
            text=f"Do you approve this submission (ID: {submission_id})?",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("Approve", callback_data=f"approve_{submission_id}"),
                    InlineKeyboardButton("Reject", callback_data=f"reject_{submission_id}")
                ]
            ])
        )

    return ConversationHandler.END

# Add this new handler for resubmissions
async def handle_resubmission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "submit_another":
        # Keep the nickname but start a new submission
        await query.message.reply_text(
            f"Great! Let's submit another food combo with nickname '{context.user_data.get('nickname')}'.\n\n"
            f"How many pictures do you have of your food combo? (e.g., '3')"
        )
        return IMAGE_COUNT
    else:
        await query.message.reply_text(
            "Thank you for your submissions! You can always submit more later by typing /start."
        )
        return ConversationHandler.END
