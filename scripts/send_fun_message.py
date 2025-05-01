#!/usr/bin/env python3
"""One-time script to send a fun 'blocked' message to a specific user."""

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

# Target user ID
TARGET_USER_ID = 1386563280

async def send_fun_message():
    """Send fun 'blocked' message to specific user."""
    # Initialize bot
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    # Prepare the fun message
    message = (
        "🚫 *YOUR ACCESS HAS BEEN TEMPORARILY SUSPENDED\\!* 🚫\n\n"
        "So you think you can just give \"constructive feedback\" about MY bot?\\! 😤\n\n"
        "Listen here, running genius\\! I didn't stay up until 4AM coding this masterpiece "
        "just to hear your \"suggestions for improvement\"\\! 💻😡\n\n"
        "Your account is now in *TIMEOUT MODE* until you acknowledge the TRUTH\\:\n\n"
        "\"*ZETT BOT IS THE BEST\\!*\" 🤖👑\n\n"
        "Until then, I've replaced all your running metrics with those of a sleepy sloth\\! 🦥⏱️\n\n"
        "\\(Obviously this is just for laughs\\! Your feedback is actually appreciated, "
        "but I couldn't resist this joke\\! 😂\\)"
    )
    
    try:
        await app.bot.send_message(
            chat_id=TARGET_USER_ID,
            text=message,
            parse_mode='MarkdownV2'
        )
        logger.info(f"Successfully sent fun 'blocked' message to user {TARGET_USER_ID}")
    except Exception as e:
        logger.error(f"Failed to send message to user {TARGET_USER_ID}: {str(e)}")
            
    # Close the application
    await app.shutdown()

if __name__ == '__main__':
    asyncio.run(send_fun_message())