#!/usr/bin/env python3
"""One-time script to broadcast a fun update message to all bot users."""

import asyncio
import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()
BOT_TOKEN = os.getenv('TELE_BOT_KEY')
if not BOT_TOKEN:
    raise ValueError("TELE_BOT_KEY not found in .env file")

async def broadcast_update():
    """Send fun update message to all users."""
    # Initialize bot
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Get all user IDs from encrypted files
    storage_dir = Path.home() / '.garmin_bot' / 'credentials'
    if not storage_dir.exists():
        logger.error("Storage directory does not exist")
        return
        
    user_ids = []
    for file in storage_dir.glob('*.enc'):
        try:
            user_id = int(file.stem)
            user_ids.append(user_id)
        except ValueError:
            logger.error(f"Invalid user ID from filename: {file.name}")
            continue
    
    logger.info(f"Found {len(user_ids)} users")
    
    message = (
        "🤖 *Breaking News\\!* 📢\n\n"
        "While you were out there crushing your workouts, our developer Zett has been "
        "living on coffee and code, working harder than a treadmill during training\\! 🏃‍♂️☕️\n\n"
        "He's been up so late that his keyboard started complaining about overtime\\! ⌨️😴\n\n"
        "Want to see what all this caffeine\\-fueled coding resulted in?\n"
        "Just hit `/start` and prepare to be amazed\\! ✨\n\n"
        "\\(Warning: New interface may cause excessive motivation and random bursts of running\\! 🏃‍♂️💨\\)"
    )

    # Send message to each user
    success_count = 0
    fail_count = 0
    
    for user_id in user_ids:
        try:
            await app.bot.send_message(
                chat_id=user_id,
                text=message,
                parse_mode='MarkdownV2'
            )
            success_count += 1
            logger.info(f"Successfully sent update message to user {user_id}")
        except Exception as e:
            fail_count += 1
            logger.error(f"Failed to send update message to user {user_id}: {str(e)}")
            
    logger.info(f"Broadcast complete. Success: {success_count}, Failed: {fail_count}")
    
    # Close the application
    await app.shutdown()

if __name__ == '__main__':
    asyncio.run(broadcast_update())
