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
BOT_TOKEN = "7868546308:AAGJFibceJv0fcUtfStIXRYeR0VeykcxrJ0"#os.getenv('TELE_BOT_KEY')
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
        "🚨 *EMERGENCY BROADCAST\\!* 🚨\n\n"
        "**The Great AI Coach Revolution \\- NOW LIVE\\!**\n\n"
        "📖 *Chapter 1: Marco's Shocking Discovery*\n"
        "Marco found a MASSIVE bug\\! The AI was mixing up long\\-term memory data between users "
        "like me accidentally mixing my indica and sativa strains \\- totally defeating the purpose of my precise medical dosing\\! 🌿😵\n\n"
        "📖 *Chapter 2: Zett's 4\\-Hour Coding Sprint*\n"
        "Armed with determination and some \\*questionable\\* indica/sativa fuel 🌿😅, "
        "I went into beast mode for a 4\\-hour coding marathon yesterday\\!\n\n"
        "📖 *Chapter 3: The Great Architecture Switch*\n"
        "Ditched the old system and switched to something WAY better\\. "
        "Think upgrading from a rusty bike to a Ferrari\\! 🏎️💨\n\n"
        "🎉 **THE EPIC RESULTS:**\n\n"
        "**🔥 Bye\\-Bye Two\\-Step Dance\\!**\n"
        "That annoying `/generate` \\+ weekplan combo? DESTROYED\\! "
        "Meet your new single\\-command superhero: `/coach`\\!\n\n"
        "**🧠 Dual\\-Context Intelligence \\- The Game Changer\\!**\n"
        "The AI now collects TWO crucial pieces of intel before analyzing your data:\n\n"
        "**🔍 Analysis Context** \\(What's affecting your body right now?\\)\n"
        "Tell the AI about current factors that might skew your data interpretation:\n"
        "• \\\"Recovering from flu last week, HRV still low\\\"\n"
        "• \\\"Work stress through the roof, sleep quality terrible\\\"\n"
        "• \\\"Started new indica medication that affects heart rate\\\"\n"
        "• \\\"Jet lag from travel, all metrics are wonky\\\"\n\n"
        "**📅 Planning Context** \\(What constraints shape your training?\\)\n"
        "Share your real\\-world limitations and goals:\n"
        "• \\\"Only 45min sessions, gym closes early\\\"\n"
        "• \\\"Focus on 10K speed, race in 6 weeks\\\"\n"
        "• \\\"Avoiding high intensity, recovering from injury\\\"\n"
        "• \\\"Training for Ironman, need periodization focus\\\"\n\n"
        "This dual context makes the AI recommendations laser\\-focused and actually useful\\!\n\n"
        "**💎 BREAKING: Behind\\-the\\-Scenes Access\\!**\n"
        "For the FIRST TIME EVER, you get the raw AI agent insights\\!\n"
        "• Metrics analysis \\(markdown\\)\n"
        "• Activity interpretation \\(markdown\\)\n"
        "• Physiology breakdown \\(markdown\\)\n"
        "• Season planning \\(markdown\\)\n"
        "Plus your usual HTML reports\\!\n\n"
        "**🔒 Fort Knox Security**\n"
        "Your data stays YOURS\\. No more accidental cross\\-contamination\\!\n\n"
        "🚀 **IT'S LIVE RIGHT NOW\\!**\n"
        "\\(Still one coach request per day because I'm not running a charity 😏\\)\n\n"
        "Ready? Try `/coach` and prepare to be blown away\\! 🚀💪"
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
