from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, filters
import os
import logging
from dotenv import load_dotenv
import uuid
from datetime import datetime
import sqlalchemy as db
from sqlalchemy.orm import sessionmaker, declarative_base
from telegram.request import HTTPXRequest
# Load environment variables
load_dotenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHANNEL_ID = os.getenv('CHANNEL_ID')
ADMIN_IDS = [int(id) for id in os.getenv('ADMIN_IDS').split(',')]

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Define conversation states
START, NICKNAME, IMAGE_COUNT, UPLOAD_IMAGES, UPLOAD_CHECK, PEOPLE_COUNT, DELIVERY_SOURCE, CONFIRM = range(8)

# Database setup
Base = declarative_base()
engine = db.create_engine(os.getenv('DATABASE_URL'))
Session = sessionmaker(bind=engine)

# Define database models
class User(Base):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, unique=True)
    nickname = db.Column(db.String)
    join_date = db.Column(db.DateTime, default=datetime.now)

class Submission(Base):
    __tablename__ = 'submissions'
    
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.String, unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    nickname = db.Column(db.String)
    image_count = db.Column(db.Integer)
    people_count = db.Column(db.Integer)
    delivery_source = db.Column(db.String)
    status = db.Column(db.String, default='pending')  # pending, approved, rejected
    created_at = db.Column(db.DateTime, default=datetime.now)
    channel_post_id = db.Column(db.Integer, nullable=True)  # ID of the post in the channel, if approved

class Image(Base):
    __tablename__ = 'images'
    
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.String, db.ForeignKey('submissions.submission_id'))
    file_id = db.Column(db.String)
    is_check_image = db.Column(db.Boolean, default=False)
    sequence = db.Column(db.Integer, nullable=True)

# Create tables
Base.metadata.create_all(engine)

# Helper functions
async def is_admin(user_id):
    return user_id in ADMIN_IDS

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

# Add this command to allow users to change their nickname
async def change_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Please enter your new nickname that will be used for your posts."
    )
    return NICKNAME
# Admin handlers
async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
# Admin command to delete a post
async def delete_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

# Admin command to list pending submissions
async def list_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

# Cancel handler
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operation cancelled. Type /start to begin again.")
    return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

def main():
    request = HTTPXRequest()
    application = Application.builder().token(TOKEN).request(request).build()

    # Conversation handler for user submission flow
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CommandHandler('new', start),  # Add alternative command
            CommandHandler('nickname', change_nickname)  # Add nickname change command
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

    # Add handlers to the application
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CallbackQueryHandler(admin_action, pattern=r'^(approve|reject)_'))
    application.add_handler(CallbackQueryHandler(handle_resubmission, pattern=r'^(submit_another|no_more_submissions)$'))
    application.add_handler(CommandHandler('delete', delete_post))
    application.add_handler(CommandHandler('pending', list_pending))

    # Start polling
    application.run_polling()
if __name__ == '__main__':
    main()