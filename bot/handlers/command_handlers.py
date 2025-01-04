"""Basic command handlers for the Telegram bot."""

import logging
from datetime import date
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

# Configure logging
logger = logging.getLogger(__name__)

from bot.formatters import escape_markdown
from core.security import SecureCredentialManager, SecureCompetitionManager, StorageError

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /start command."""
    user_name = update.effective_user.first_name
    await update.message.reply_text(
        escape_markdown(f"Hey {user_name}! 🏃‍♂️ Welcome to your AI Training Assistant!\n\n") +
        "*Available Commands:*\n\n" +
        "🔐 *Getting Started:*\n" +
        "• `/login` \\- Connect your Garmin account \\(credentials stored securely\\)\n\n" +
        "📊 *Main Features:*\n" +
        "• `/generate` \\- Get AI\\-powered training insights\n" +
        "• `/workout` \\- Get discipline\\-specific workout suggestions\n\n" +
        "🏃‍♂️ *Competition Management:*\n" +
        "• `/races` \\- View your race calendar\n" +
        "• `/addrace` \\- Add a new competition\n" +
        "• `/editrace` \\- Modify competition details\n" +
        "• `/delrace` \\- Remove a competition\n\n" +
        "ℹ️ *Other:*\n" +
        "• `/roadmap` \\- View upcoming features\n" +
        "• `/help` \\- Show detailed command overview\n\n" +
        "🔒 *Security Note:*\n" +
        "• Your credentials are only used to fetch data from Garmin\n" +
        "• All credentials are stored securely with encryption\n" +
        "• All communication is encrypted\n" +
        "• Created by Zett with privacy in mind 🛡️\n\n" +
        "Ready to start\\? Use `/help` to see all commands or `/login` to connect your Garmin account\\! 🚀",
        parse_mode=ParseMode.MARKDOWN_V2
    )

async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /help command."""
    await update.message.reply_text(
        "🤖 *Available Commands*\n\n" +
        "🔐 *Authentication*\n" +
        "• `/login` \\- Connect your Garmin account \\(credentials stored securely\\)\n" +
        "• `/clear_credentials` \\- Remove stored credentials\n\n" +
        "📊 *Training Features*\n" +
        "• `/generate` \\- Get personalized training insights\n" +
        "• `/workout` \\- Get discipline\\-specific workout suggestions\n\n" +
        "🏃‍♂️ *Competition Management*\n" +
        "• `/races` \\- View your race calendar\n" +
        "• `/addrace` \\- Add a new competition\n" +
        "• `/editrace` \\- Modify competition details\n" +
        "• `/delrace` \\- Remove a competition \\(format: YYYY\\-MM\\-DD\\)\n\n" +
        "ℹ️ *Other Commands*\n" +
        "• `/roadmap` \\- View upcoming features\n" +
        "• `/help` \\- Show this command overview\n\n" +
        "🔒 *Security Note*\n" +
        "Your credentials are stored securely with encryption\\.",
        parse_mode=ParseMode.MARKDOWN_V2
    )

async def roadmap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /roadmap command."""
    await update.message.reply_text(
        "🗺️ *Development Roadmap*\n\n" +
        "*Coming Soon\\:*\n\n" +
        "1️⃣ *General Training Q&A*\n" +
        "• Ask training\\-related questions without Garmin data\n" +
        "• Get expert advice on training principles\n" +
        "• Discuss injury prevention and recovery\n\n" +
        "2️⃣ *Smart Workout Suggestions*\n" +
        "• Daily workout recommendations based on your data\n" +
        "• Adaptive training plans\n" +
        "• Recovery\\-based intensity adjustments\n\n" +
        "Stay tuned for these exciting updates\\! 🚀",
        parse_mode=ParseMode.MARKDOWN_V2
    )

async def clear_credentials(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /clear_credentials command."""
    user_id = update.effective_user.id
    cred_manager = SecureCredentialManager(user_id)
    
    if cred_manager.clear():
        await update.message.reply_text(
            "✅ Your stored credentials have been cleared\\.\n" +
            "Use `/login` to set up new credentials\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
    else:
        await update.message.reply_text(
            "❌ Failed to clear credentials\\. Please try again or contact support\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )

async def races(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /races command - List upcoming competitions."""
    user_id = update.effective_user.id
    comp_manager = SecureCompetitionManager(user_id)
    
    try:
        upcoming = comp_manager.get_upcoming_competitions()
        
        if not upcoming:
            await update.message.reply_text(
                "📅 *No upcoming races scheduled*\n\n" +
                "Use `/addrace` to add a competition to your calendar\\!",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            return
            
        # Format races by priority
        races_by_priority = {"A": [], "B": [], "C": []}
        for race in upcoming:
            races_by_priority[race.priority.value].append(race)
            
        response = "🏃‍♂️ *Your Race Calendar*\n\n"
        
        for priority in ["A", "B", "C"]:
            if races_by_priority[priority]:
                response += f"*Priority {priority} Races:*\n"
                for race in races_by_priority[priority]:
                    date_str = race.date.strftime("%Y-%m-%d")
                    response += (
                        f"• {escape_markdown(date_str)} \\- "
                        f"{escape_markdown(race.name)} "
                        f"\\({escape_markdown(race.race_type)}\\)"
                    )
                    if race.target_time:
                        response += f" \\- Goal: {escape_markdown(race.target_time)}"
                    response += "\n"
                response += "\n"
        
        response += "_Use_ `/addrace` _to add more competitions\\!_"
        
        await update.message.reply_text(
            response,
            parse_mode=ParseMode.MARKDOWN_V2
        )
        
    except Exception:
        await update.message.reply_text(
            "❌ Failed to retrieve race calendar\\. Please try again\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )

async def delrace(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /delrace command - Remove a competition."""
    message_text = update.message.text.strip()
    user_id = update.effective_user.id
    logger.info(f"Processing delrace command for user {user_id}: {message_text}")
    
    # Extract date from command
    # Handle both "/delrace 2024-06-30" and just "2024-06-30" formats
    parts = message_text.split()
    if len(parts) < 2:
        # First check if user has any races
        comp_manager = SecureCompetitionManager(user_id)
        upcoming = comp_manager.get_upcoming_competitions()
        
        if not upcoming:
            await update.message.reply_text(
                "📅 *No races in your calendar*\n\n" +
                "Use `/addrace` to add a competition\\!",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            return
            
        # Show available races to delete
        response = (
            "❌ Please provide the date of the race to delete \\(YYYY\\-MM\\-DD\\)\n" +
            "Example: `/delrace 2024\\-06\\-30`\n\n" +
            "*Available Races:*\n"
        )
        
        for race in upcoming:
            date_str = race.date.strftime("%Y-%m-%d")
            response += (
                f"• {escape_markdown(date_str)} \\- "
                f"{escape_markdown(race.name)} "
                f"\\({escape_markdown(race.race_type)}\\)\n"
            )
        
        await update.message.reply_text(
            response,
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return
    
    try:
        # Get the date part (last part of the command)
        date_str = parts[-1].strip()
        logger.info(f"Attempting to delete race on date: {date_str}")
        
        race_date = date.fromisoformat(date_str)
        comp_manager = SecureCompetitionManager(user_id)
        
        # First verify the race exists
        race = comp_manager.get_competition(race_date)
        if not race:
            logger.info(f"No race found for date {date_str}")
            
            # Check if there are any races to suggest
            upcoming = comp_manager.get_upcoming_competitions()
            if upcoming:
                response = (
                    "❌ No race found on that date\\.\n\n"
                    "*Available Races:*\n"
                )
                for race in upcoming:
                    date_str = race.date.strftime("%Y-%m-%d")
                    response += (
                        f"• {escape_markdown(date_str)} \\- "
                        f"{escape_markdown(race.name)} "
                        f"\\({escape_markdown(race.race_type)}\\)\n"
                    )
            else:
                response = (
                    "❌ No races found in your calendar\\.\n\n"
                    "Use `/addrace` to add a competition\\!"
                )
                
            await update.message.reply_text(
                response,
                parse_mode=ParseMode.MARKDOWN_V2
            )
            return
        
        logger.info(f"Found race to delete: {race.name} on {race.date}")
        
        # Store race details before deletion
        race_details = {
            "date": race.date.strftime("%Y-%m-%d"),
            "name": race.name,
            "type": race.race_type,
            "priority": race.priority.value,
            "target_time": race.target_time,
            "location": race.location
        }
        
        # Attempt deletion
        deletion_success = comp_manager.delete_competition(race_date)
        
        if deletion_success:
            logger.info(f"Successfully deleted race: {race_details}")
            
            # Create detailed success message
            success_message = (
                "✅ Successfully deleted race:\n\n"
                f"• *Date:* {escape_markdown(race_details['date'])}\n"
                f"• *Name:* {escape_markdown(race_details['name'])}\n"
                f"• *Type:* {escape_markdown(race_details['type'])}\n"
                f"• *Priority:* {escape_markdown(race_details['priority'])}"
            )
            
            # Add optional fields if they were set
            if race_details['target_time']:
                success_message += f"\n• *Target:* {escape_markdown(race_details['target_time'])}"
            if race_details['location']:
                success_message += f"\n• *Location:* {escape_markdown(race_details['location'])}"
                
            # Add remaining races count
            remaining = comp_manager.get_upcoming_competitions()
            if remaining:
                success_message += f"\n\n_You have {len(remaining)} remaining races in your calendar\\._"
            else:
                success_message += "\n\n_Your race calendar is now empty\\. Use_ `/addrace` _to add competitions\\!_"
            
            await update.message.reply_text(
                success_message,
                parse_mode=ParseMode.MARKDOWN_V2
            )
            
            # Verify deletion
            verification = comp_manager.get_competition(race_date)
            if verification is None:
                logger.info("Deletion verification successful")
            else:
                logger.error("Race still exists after deletion")
                
        else:
            logger.error(f"Failed to delete race on date {date_str}")
            await update.message.reply_text(
                "❌ Failed to delete race\\. Please try again\\.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            
    except ValueError as ve:
        logger.error(f"Invalid date format: {str(ve)}")
        await update.message.reply_text(
            "❌ Invalid date format\\. Please use YYYY\\-MM\\-DD\n" +
            "Example: `2024\\-06\\-30`",
            parse_mode=ParseMode.MARKDOWN_V2
        )
    except StorageError as se:
        logger.error(f"Storage error in delrace: {str(se)}")
        await update.message.reply_text(
            "❌ Failed to delete race due to storage error\\. Please try again\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
    except Exception as e:
        logger.error(f"Unexpected error in delrace: {str(e)}")
        await update.message.reply_text(
            "❌ Failed to delete race\\. Please try again\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
