#!/usr/bin/env python3
"""Script to list users who have interacted with the bot and explain how to get all Telegram users."""

import os
import sys
from pathlib import Path
import logging
from telegram import Bot
from telegram.ext import ApplicationBuilder
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add project root to Python path
project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)

from core.security.users import UserTracker

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def get_all_telegram_users(bot_token):
    """Get all users who have interacted with the bot through Telegram."""
    bot = Bot(bot_token)
    
    print("\n2. All Telegram Bot Users (last 24 hours):")
    print("-------------------------------------------")
    try:
        # Get updates from the last 24 hours
        updates = await bot.get_updates(offset=-1, timeout=1)
        if updates:
            unique_users = set()
            for update in updates:
                if update.effective_user:
                    user = update.effective_user
                    unique_users.add((user.id, user.first_name, user.username))
            
            if unique_users:
                print(f"\nFound {len(unique_users)} unique Telegram users:")
                for user_id, first_name, username in sorted(unique_users):
                    print(f"User ID: {user_id}, Name: {first_name}, Username: {username or 'N/A'}")
            else:
                print("\nNo Telegram users found in recent updates.")
        else:
            print("\nNo recent bot interactions found.")
            
        print("\nNote: This only shows users from recent interactions.")
        print("To get a complete list of all users who have ever interacted with your bot:")
        print("1. Use Telegram Bot API's getUpdates with longer timeframes")
        print("2. Consider implementing a database to store user interactions")
        print("3. Add user tracking in the bot's start command handler")
        
    except Exception as e:
        print(f"\nError getting Telegram updates: {e}")
        print("Make sure your bot token is correct and the bot is running.")

def list_garmin_users():
    """List users who have Garmin data stored."""
    # Base directory for bot storage
    storage_dir = Path.home() / '.garmin_bot'
    
    print("\n1. Users with Garmin Data:")
    print("-------------------------")
    
    if not storage_dir.exists():
        print("\nNo storage directory found. No users have stored Garmin data yet.")
        return
    
    # Check each storage type directory
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
        print(f"\nFound {total_users} users with Garmin data:")
        for user_id in sorted(unique_users):
            print(f"User ID: {user_id}")
    else:
        print("\nNo users found with Garmin data.")

def list_tracked_users():
    """List all users who have ever interacted with the bot."""
    print("\n3. All Tracked Bot Users:")
    print("------------------------")
    
    tracker = UserTracker()
    users = tracker.get_all_users()
    
    if users:
        print(f"\nFound {len(users)} users who have interacted with the bot:")
        for user in users:
            print(f"\nUser ID: {user['user_id']}")
            print(f"Name: {user['first_name']}")
            print(f"Username: {user.get('username', 'N/A')}")
            print(f"First seen: {user['first_seen']}")
            print(f"Last seen: {user['last_seen']}")
            print(f"Total interactions: {user['interaction_count']}")
    else:
        print("\nNo tracked users found.")
        print("Users will be tracked when they interact with the bot.")

async def main():
    """Main function to list all types of users."""
    # Load environment variables from .env file
    load_dotenv()
    
    print("\nListing Bot Users")
    print("================")
    
    # List users with Garmin data
    list_garmin_users()
    
    # Try to get recent Telegram users if token is available
    bot_token = os.getenv('TELE_BOT_KEY')
    if bot_token:
        await get_all_telegram_users(bot_token)
    else:
        print("\n2. Telegram Bot Users:")
        print("----------------------")
        print("\nError: TELE_BOT_KEY not found in .env file")
    
    # List all tracked users
    list_tracked_users()

if __name__ == '__main__':
    asyncio.run(main())
