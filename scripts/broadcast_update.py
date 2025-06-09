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
BOT_TOKEN = "7824020130:AAHRPI_Ti1USD_QDzDybvYJHF0ByhztXmVE"#os.getenv('TELE_BOT_KEY')
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
        "**AI Architecture Migration \\- LIVE\\!**\n\n"
        "📖 *The Bug Discovery*\n"
        "Marco found a catastrophic cross\\-user data leak\\! Like accidentally mixing my indica/sativa strains \\- "
        "completely defeating my precisely titrated medical dosing protocols\\! 🌿😵💻\n\n"
        "📖 *The 12\\-Hour Fix*\n"
        "Armed with questionable indica/sativa debugging fuel 🌿😅 and caffeine, "
        "I went full\\-stack beast mode for a hardcore refactoring marathon\\!\n\n"
        "📖 *CrewAI → LangChain Migration*\n"
        "Rewrote the entire multi\\-agent system\\. Monolithic → microservices\\! 🏗️⚡\n\n"
        "🎉 **THE RESULTS:**\n\n"
        "**🔥 Single `/coach` Command\\!**\n"
        "That janky `/generate` \\+ weekplan combo? DEPRECATED\\!\n\n"
        "**🧠 Dual\\-Context System**\n\n"
        "**Analysis Context** \\(tells AI how to interpret your data\\):\n"
        "\\\"Recovering from flu, sleep terrible from work stress, new indica strain affecting my resting heart rate\\\"\n\n"
        "**Planning Context** \\(defines constraints for your training plan\\):\n"
        "\\\"Only 45min sessions because gym closes early, focusing on 10K speed for race in 6 weeks, avoiding high intensity due to knee issues\\\"\n\n"
        "**🎨 GAME CHANGER: AI Plotting Engine\\!**\n"
        "AI agents now write custom Python code for interactive Plotly visualizations\\! "
        "They create charts tailored to YOUR specific data \\- no templates, pure AI creativity\\!\n\n"
        "**Integration Magic:**\n"
        "Plots auto\\-embed in HTML reports\\. Agents reference each other's visualizations for comprehensive insights\\!\n\n"
        "**⚠️ Note:** Interactive plots work best on computers\\. Mobile may fail to display\\.\n\n"
        "**🚀 LIVE PROGRESS THEATER\\!**\n"
        "Watch the AI brain at work\\! Real\\-time updates show you EXACTLY what's happening:\n"
        "• Which agent is executing \\(Metrics, Physiology, Weekly Planner, etc\\.\\)\n"
        "• Live plot generation notifications \\(\\\"📈 VO2 Max trend created\\!\\\"\\)\n"
        "• Visual progress bars \\+ execution stats\n"
        "• Tool usage tracking \\(because nerds love metrics\\! 🤓\\)\n\n"
        "**No more black\\-box waiting\\!** You see the 10\\-agent orchestration unfold in real\\-time\\. "
        "It's like watching a Formula 1 pit crew, but for your training data\\! 🏎️⚡\n\n"
        "**� Raw Agent Outputs:**\n"
        "Get markdown files \\+ custom plots from all 4 AI agents \\+ HTML reports\\!\n\n"
        "**🔒 Military\\-Grade Isolation**\n"
        "Zero cross\\-user contamination\\!\n\n"
        "**🧪 BETA TEST TODAY AFTER MEDICATION\\!**\n"
        "ONE user gets first plotting system test when I'm back from my run\\! 🏃‍♂️✨\n\n"
        "Ready? Try `/coach` then\\! 🚀💪"
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
