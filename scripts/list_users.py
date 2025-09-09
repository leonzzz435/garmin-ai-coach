#!/usr/bin/env python3

import asyncio
import logging
import os
import sys
from pathlib import Path

project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from dotenv import load_dotenv
from telegram import Bot

from core.security.users import UserTracker

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)


async def get_all_telegram_users(bot_token):
    bot = Bot(bot_token)

    logger.info("\n2. All Telegram Bot Users (last 24 hours):")
    logger.info("-------------------------------------------")
    try:
        updates = await bot.get_updates(offset=-1, timeout=1)
        if updates:
            unique_users = set()
            for update in updates:
                if update.effective_user:
                    user = update.effective_user
                    unique_users.add((user.id, user.first_name, user.username))

            if unique_users:
                logger.info(f"\nFound {len(unique_users)} unique Telegram users:")
                for user_id, first_name, username in sorted(unique_users):
                    logger.info(
                        f"User ID: {user_id}, Name: {first_name}, Username: {username or 'N/A'}"
                    )
            else:
                logger.info("\nNo Telegram users found in recent updates.")
        else:
            logger.info("\nNo recent bot interactions found.")

        logger.info("\nNote: This only shows users from recent interactions.")
        logger.info("To get a complete list of all users who have ever interacted with your bot:")
        logger.info("1. Use Telegram Bot API's getUpdates with longer timeframes")
        logger.info("2. Consider implementing a database to store user interactions")
        logger.info("3. Add user tracking in the bot's start command handler")

    except Exception as e:
        logger.info(f"\nError getting Telegram updates: {e}")
        logger.info("Make sure your bot token is correct and the bot is running.")


def list_garmin_users():
    # Base directory for bot storage
    storage_dir = Path.home() / '.garmin_bot'

    logger.info("\n1. Users with Garmin Data:")
    logger.info("-------------------------")

    if not storage_dir.exists():
        logger.info("\nNo storage directory found. No users have stored Garmin data yet.")
        return

    storage_types = ['credentials', 'reports']
    unique_users = set()

    for storage_type in storage_types:
        type_dir = storage_dir / storage_type
        if not type_dir.exists():
            continue

        # List all .enc files (user files)
        for file in type_dir.glob('*.enc'):
            # Extract user ID from filename (remove .enc extension)
            user_id = file.stem
            unique_users.add(user_id)

    # Print results
    total_users = len(unique_users)
    if total_users > 0:
        logger.info(f"\nFound {total_users} users with Garmin data:")
        for user_id in sorted(unique_users):
            logger.info(f"User ID: {user_id}")
    else:
        logger.info("\nNo users found with Garmin data.")


def list_tracked_users():
    logger.info("\n3. All Tracked Bot Users:")
    logger.info("------------------------")

    tracker = UserTracker()
    users = tracker.get_all_users()

    if users:
        logger.info(f"\nFound {len(users)} users who have interacted with the bot:")
        for user in users:
            logger.info(f"\nUser ID: {user['user_id']}")
            logger.info(f"Name: {user['first_name']}")
            logger.info(f"Username: {user.get('username', 'N/A')}")
            logger.info(f"First seen: {user['first_seen']}")
            logger.info(f"Last seen: {user['last_seen']}")
            logger.info(f"Total interactions: {user['interaction_count']}")
    else:
        logger.info("\nNo tracked users found.")
        logger.info("Users will be tracked when they interact with the bot.")


async def main():
    # Load environment variables from .env file
    load_dotenv()

    logger.info("\nListing Bot Users")
    logger.info("================")

    # List users with Garmin data
    list_garmin_users()

    bot_token = os.getenv('TELE_BOT_KEY')
    if bot_token:
        await get_all_telegram_users(bot_token)
    else:
        logger.info("\n2. Telegram Bot Users:")
        logger.info("----------------------")
        logger.info("\nError: TELE_BOT_KEY not found in .env file")

    # List all tracked users
    list_tracked_users()


if __name__ == '__main__':
    asyncio.run(main())
