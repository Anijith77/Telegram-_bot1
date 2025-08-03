import os
import logging

# Bot configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")

# File size limits (Updated limits)
MAX_PHOTO_SIZE = 200 * 1024 * 1024  # 200MB for photos
MAX_VIDEO_SIZE = 3 * 1024 * 1024 * 1024  # 3GB for videos
MAX_DOCUMENT_SIZE = 3 * 1024 * 1024 * 1024  # 3GB for documents

# Auto-delete settings
AUTO_DELETE_AFTER_HOURS = 1  # Delete files after 1 hour

# Download settings
DOWNLOAD_TIMEOUT = 30  # seconds
MAX_RETRIES = 3
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

# Supported formats
SUPPORTED_IMAGE_FORMATS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
SUPPORTED_VIDEO_FORMATS = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.m4v'}

# Logging configuration
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
