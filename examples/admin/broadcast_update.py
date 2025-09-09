#!/usr/bin/env python3

import asyncio
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()
BOT_TOKEN = os.getenv("TELE_BOT_KEY")
if not BOT_TOKEN:
    raise ValueError("Set TELE_BOT_KEY in environment or .env file")


async def broadcast_update():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

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
        "System broadcast\n\n"
        "- Title: <enter title>\n"
        "- Summary: <enter summary>\n"
        "- Details: <enter details>\n\n"
        "This is a template message from examples/admin/broadcast_update.py.\n"
    )

    # Send message to each user
    success_count = 0
    fail_count = 0

    for user_id in user_ids:
        try:
            await app.bot.send_message(chat_id=user_id, text=message, parse_mode='MarkdownV2')
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
