"""
Main bot logic for Telegram Media Extractor Bot
Upload this file to GitHub as: bot.py
"""

import asyncio
import os
import re
import time
import threading
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError
from media_extractor import MediaExtractor
from config import TELEGRAM_BOT_TOKEN, MAX_PHOTO_SIZE, MAX_VIDEO_SIZE, AUTO_DELETE_AFTER_HOURS, logger
from utils import cleanup_temp_file, validate_url, is_image, is_video
from PIL import Image


class TelegramMediaBot:

    def __init__(self):
        self.media_extractor = MediaExtractor()
        self.application = Application.builder().token(
            TELEGRAM_BOT_TOKEN).build()
        self.sent_messages = {}  # Track sent messages for auto-deletion
        self._setup_handlers()
        self._start_auto_delete_timer()

    def _start_auto_delete_timer(self):
        """Start the auto-delete timer for sent messages"""

        def auto_delete_worker():
            while True:
                current_time = time.time()
                delete_threshold = AUTO_DELETE_AFTER_HOURS * 3600  # Convert hours to seconds

                messages_to_delete = []
                for message_key, message_info in self.sent_messages.items():
                    if current_time - message_info[
                            'sent_time'] > delete_threshold:
                        messages_to_delete.append(message_key)

                # Check for messages to warn (5 minutes before deletion)
                warn_threshold = delete_threshold - 300  # 5 minutes before deletion
                for message_key, message_info in list(
                        self.sent_messages.items()):
                    time_elapsed = current_time - message_info['sent_time']

                    # Send warning if 5 minutes left and not already warned
                    if (time_elapsed > warn_threshold
                            and time_elapsed < delete_threshold
                            and not message_info.get('warned', False)):

                        try:
                            asyncio.create_task(
                                self._send_deletion_warning(
                                    message_info['chat_id'],
                                    message_info['filename']))
                            self.sent_messages[message_key]['warned'] = True
                            logger.info(
                                f"Sent deletion warning for {message_key}")
                        except Exception as e:
                            logger.error(
                                f"Error sending deletion warning: {e}")

                # Delete expired messages
                for message_key in messages_to_delete:
                    try:
                        message_info = self.sent_messages[message_key]
                        asyncio.create_task(
                            self._delete_message(message_info['chat_id'],
                                                 message_info['message_id']))
                        del self.sent_messages[message_key]
                        logger.info(
                            f"Scheduled deletion of message {message_key}")
                    except Exception as e:
                        logger.error(f"Error scheduling message deletion: {e}")

                # Check every 10 minutes
                time.sleep(600)

        delete_thread = threading.Thread(target=auto_delete_worker,
                                         daemon=True)
        delete_thread.start()

    async def _delete_message(self, chat_id: int, message_id: int):
        """Delete a message"""
        try:
            await self.application.bot.delete_message(chat_id=chat_id,
                                                      message_id=message_id)
            logger.info(f"Deleted message {message_id} from chat {chat_id}")
        except Exception as e:
            logger.warning(f"Failed to delete message {message_id}: {e}")

    async def _send_deletion_warning(self, chat_id: int, filename: str):
        """Send warning message before deletion"""
        try:
            warning_text = f"⚠️ **Auto-Delete Warning**\n\nYour media file `{filename}` will be automatically deleted in 5 minutes for privacy protection.\n\nIf you need to keep it, please save it now!"
            await self.application.bot.send_message(chat_id=chat_id,
                                                    text=warning_text,
                                                    parse_mode='Markdown')
            logger.info(
                f"Sent deletion warning for {filename} to chat {chat_id}")
        except Exception as e:
            logger.warning(f"Failed to send deletion warning: {e}")

    def _setup_handlers(self):
        """Setup bot command and message handlers"""
        # Command handlers
        self.application.add_handler(
            CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))

        # Message handlers
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND,
                           self.handle_url_message))

    async def start_command(self, update: Update,
                            context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        welcome_message = """
🤖 **Media Extractor Bot**

Hi! I can help you extract images and videos from web links.

**How to use:**
1. Send me any web URL
2. I'll scan it for images and videos
3. I'll send back any media I find

**Supported formats:**
• Images: JPG, PNG, GIF, WebP, BMP
• Videos: MP4, AVI, MOV, MKV, WebM, M4V

**Commands:**
• /help - Show this help message
• /start - Start the bot

Just paste any URL and I'll do the rest! 🚀
        """

        await update.message.reply_text(welcome_message, parse_mode='Markdown')
        logger.info(f"User {update.effective_user.id} started the bot")

    async def help_command(self, update: Update,
                           context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_message = """
🆘 **Help - Media Extractor Bot**

**How it works:**
Send me any web URL and I'll extract images and videos from it.

**Supported websites:**
• Direct media links (images/videos)
• YouTube, Vimeo, and other video platforms
• Social media posts with embedded media
• News articles with images
• Any website with embedded media

**File size limits:**
• Images: Up to 10MB
• Videos: Up to 50MB

**Tips:**
• Make sure the URL is accessible and public
• Some websites may block automated access
• Private or login-required content won't work

**Examples:**
• `https://example.com/image.jpg`
• `https://youtube.com/watch?v=...`
• `https://news-site.com/article-with-images`

Need more help? Just send me a URL and see what happens! 🎯
        """

        await update.message.reply_text(help_message, parse_mode='Markdown')

    async def handle_url_message(self, update: Update,
                                 context: ContextTypes.DEFAULT_TYPE):
        """Handle URL messages from users"""
        user_id = update.effective_user.id
        message_text = update.message.text.strip()

        logger.info(f"User {user_id} sent: {message_text}")

        # Extract URLs from message
        urls = self._extract_urls(message_text)

        if not urls:
            await update.message.reply_text(
                "❌ No valid URLs found in your message.\n\n"
                "Please send a valid web URL (starting with http:// or https://)"
            )
            return

        # Process each URL
        for url in urls[:3]:  # Limit to 3 URLs per message
            await self._process_url(update, url)

    def _extract_urls(self, text):
        """Extract URLs from text"""
        # URL regex pattern
        url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
        urls = re.findall(url_pattern, text)

        # Validate URLs
        valid_urls = []
        for url in urls:
            if validate_url(url):
                valid_urls.append(url)

        return valid_urls

    async def _process_url(self, update: Update, url: str):
        """Process a single URL and extract media"""
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id

        # Send processing message
        processing_msg = await update.message.reply_text(
            f"🔍 Processing URL: {url[:50]}{'...' if len(url) > 50 else ''}\n"
            "Please wait while I extract media...")

        try:
            # Extract media
            media_files = self.media_extractor.extract_media_from_url(url)

            if not media_files:
                await processing_msg.edit_text(
                    f"❌ No supported media found at:\n{url}\n\n"
                    "The URL might not contain images or videos, or they might be in unsupported formats."
                )
                return

            # Update processing message
            await processing_msg.edit_text(
                f"📁 Found {len(media_files)} media file(s)!\n"
                "Uploading to Telegram...")

            # Send media files
            sent_count = 0
            for media_info in media_files:
                try:
                    success = await self._send_media_file(
                        chat_id, media_info, url)
                    if success:
                        sent_count += 1
                except Exception as e:
                    logger.error(f"Error sending media file: {e}")
                    continue
                finally:
                    # Cleanup temp file
                    cleanup_temp_file(media_info['file_path'])

            # Update final status
            if sent_count > 0:
                await processing_msg.edit_text(
                    f"✅ Successfully sent {sent_count} media file(s) from:\n{url}"
                )
            else:
                await processing_msg.edit_text(
                    f"❌ Failed to send media files from:\n{url}\n\n"
                    "Files might be too large or in unsupported format.")

        except Exception as e:
            error_message = str(e)
            logger.error(
                f"Error processing URL {url} for user {user_id}: {error_message}"
            )

            await processing_msg.edit_text(
                f"❌ Error processing URL:\n{url}\n\n"
                f"Error: {error_message}\n\n"
                "Please try with a different URL or check if the link is accessible."
            )

    def _validate_image(self, file_path: str) -> bool:
        """Validate if file is a proper image using PIL"""
        try:
            with Image.open(file_path) as img:
                img.verify()  # Verify the image is valid
            return True
        except Exception as e:
            logger.debug(f"Image validation failed for {file_path}: {e}")
            return False

    async def _send_media_file(self, chat_id: int, media_info: dict,
                               source_url: str):
        """Send a media file to chat"""
        file_path = media_info['file_path']
        filename = media_info['filename']
        file_size = media_info['size']
        media_type = media_info['type']

        # Log media type for debugging
        logger.info(
            f"Attempting to send {media_type}: {filename} ({file_size} bytes)")

        try:
            # Double-check if it's an image by file extension and validate
            if any(filename.lower().endswith(ext) for ext in
                   ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']):
                if self._validate_image(file_path):
                    media_type = 'image'
                    logger.info(
                        f"Corrected media type to 'image' based on filename and validation: {filename}"
                    )
                else:
                    media_type = 'document'
                    logger.info(
                        f"Image validation failed, sending as document: {filename}"
                    )

            # Check file size limits
            if media_type == 'image' and file_size > MAX_PHOTO_SIZE:
                # If image is too large for photo, send as document
                logger.info(
                    f"Image too large for photo ({file_size} bytes), sending as document"
                )
                media_type = 'document'
            elif media_type == 'video' and file_size > MAX_VIDEO_SIZE:
                raise ValueError(
                    f"Video too large: {file_size} bytes (max: {MAX_VIDEO_SIZE})"
                )

            # Prepare caption
            caption = f"📎 {filename}\n🔗 Source: {source_url[:100]}{'...' if len(source_url) > 100 else ''}\n⏰ Auto-deletes in {AUTO_DELETE_AFTER_HOURS} hour(s)"

            sent_message = None
            with open(file_path, 'rb') as file:
                if media_type == 'image':
                    # Send as photo
                    logger.info("Sending as photo")
                    try:
                        sent_message = await self.application.bot.send_photo(
                            chat_id=chat_id, photo=file, caption=caption)
                    except TelegramError as e:
                        if "Image_process_failed" in str(e):
                            logger.info(
                                "Image processing failed, falling back to document"
                            )
                            file.seek(0)  # Reset file pointer
                            sent_message = await self.application.bot.send_document(
                                chat_id=chat_id,
                                document=file,
                                caption=caption,
                                filename=filename)
                        else:
                            raise
                elif media_type == 'video':
                    # Send as video
                    logger.info("Sending as video")
                    sent_message = await self.application.bot.send_video(
                        chat_id=chat_id, video=file, caption=caption)
                else:
                    # Send as document
                    logger.info("Sending as document")
                    sent_message = await self.application.bot.send_document(
                        chat_id=chat_id,
                        document=file,
                        caption=caption,
                        filename=filename)

            # Track message for auto-deletion
            if sent_message:
                message_key = f"{chat_id}_{sent_message.message_id}"
                self.sent_messages[message_key] = {
                    'chat_id': chat_id,
                    'message_id': sent_message.message_id,
                    'sent_time': time.time(),
                    'filename': filename
                }

            logger.info(
                f"Successfully sent {media_type}: {filename} ({file_size} bytes)"
            )
            return True

        except TelegramError as e:
            logger.error(f"Telegram error sending {filename}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error sending {filename}: {e}")
            return False

    def run(self):
        """Run the bot"""
        logger.info("Starting Telegram Media Extractor Bot...")
        self.application.run_polling(drop_pending_updates=True,
                                     allowed_updates=Update.ALL_TYPES)
