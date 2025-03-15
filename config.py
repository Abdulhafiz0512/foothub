import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bot configuration
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHANNEL_ID = os.getenv('CHANNEL_ID')
ADMIN_IDS = [int(id) for id in os.getenv('ADMIN_IDS').split(',')]
DATABASE_URL = os.getenv('DATABASE_URL')

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Define conversation states
START, NICKNAME, IMAGE_COUNT, UPLOAD_IMAGES, UPLOAD_CHECK, PEOPLE_COUNT, DELIVERY_SOURCE, CONFIRM = range(8)