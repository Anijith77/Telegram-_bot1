# Telegram Media Extractor Bot

A Telegram bot that extracts and returns images and videos from web links.

## Features
- Extracts media from web links
- Supports images up to 200MB and videos up to 3GB
- Auto-deletes media after 1 hour for privacy
- 5-minute warning before deletion
- Multiple extraction methods (direct URLs, yt-dlp, web scraping)

## Deployment

### Environment Variables
Set these environment variables in your deployment platform:
- `TELEGRAM_BOT_TOKEN` - Your Telegram bot token from @BotFather

### For Railway/Render Deployment
1. Upload all files to GitHub
2. Connect your repository to Railway/Render
3. Set the environment variable
4. Deploy automatically

## 
Send any web link to the bot in Telegram, and it will extract and send back any images or videos found on that page.