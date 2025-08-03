#!/usr/bin/env python3
"""
Telegram Media Extractor Bot

A Telegram bot that extracts and returns images/videos from web links sent by users.
"""

import sys
import signal
import asyncio
from bot import TelegramMediaBot
from config import logger, TELEGRAM_BOT_TOKEN

def signal_handler(sig, frame):
    """Handle shutdown signals"""
    logger.info("Received shutdown signal, stopping bot...")
    sys.exit(0)

def main():
    """Main entry point"""
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Validate configuration
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set!")
        logger.error("Please set the TELEGRAM_BOT_TOKEN environment variable.")
        sys.exit(1)
    
    try:
        # Create and run bot
        bot = TelegramMediaBot()
        logger.info("Bot initialized successfully")
        
        # Start the bot
        bot.run()
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
