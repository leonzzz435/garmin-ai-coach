"""Basic command handlers for the Telegram bot."""

import logging
from datetime import date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from bot.handlers.conversation_handlers import start_login
from bot.handlers.data_handlers import generate, workout

# Configure logging
logger = logging.getLogger(__name__)

from bot.formatters import escape_markdown
from core.security import SecureCredentialManager, SecureCompetitionManager, StorageError

async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard button presses."""
    logger.debug(f"Update object: {update}")
    logger.debug(f"CallbackQuery object: {update.callback_query}")
    query = update.callback_query
    
    if not query:
        logger.error("Update does not contain a callback_query")
        return
    
    await query.answer()  # Answer callback query to remove loading state
    
    user_name = update.effective_user.first_name  # More consistent way to access user
    logger.info(f"User {user_name} triggered a button with data: {query.data}")
    
    # Map callback data to handler functions
    if query.data.startswith("help_") or query.data.startswith("roadmap_"):
        category_type, category = query.data.split("_")
        
        help_messages = {
            "auth": (
                "🔐 *Authentication Help*\n\n"
                "*Commands:*\n"
                "• `/login` \\- Connect your Garmin account\n"
                "• `/clear_credentials` \\- Remove stored credentials\n\n"
                "*Usage:*\n"
                "1\\. Use `/login` to connect your Garmin account\n"
                "2\\. Enter your email when prompted\n"
                "3\\. Enter your password \\(deleted immediately after\\)\n"
                "4\\. Use `/clear_credentials` to remove stored data\n\n"
                "*Security:*\n"
                "• Credentials are encrypted\n"
                "• Communication is secure\n"
                "• Data is stored locally"
            ),
            "training": (
                "📊 *Training Features Help*\n\n"
                "*Commands:*\n"
                "• `/generate` \\- Get AI training insights\n"
                "• `/workout` \\- Get workout suggestions\n\n"
                "*Features:*\n"
                "• Smart analysis of your training data\n"
                "• Personalized workout recommendations\n"
                "• Recovery and intensity guidance\n"
                "• Race\\-specific training plans\n\n"
                "*Tips:*\n"
                "• Keep your Garmin data up to date\n"
                "• Log all your workouts\n"
                "• Include race goals for better suggestions"
            ),
            "races": (
                "🏃‍♂️ *Race Management Help*\n\n"
                "*Commands:*\n"
                "• `/races` \\- View race calendar\n"
                "• `/addrace` \\- Add competition\n"
                "• `/editrace` \\- Edit competition\n"
                "• `/delrace` \\- Remove competition\n\n"
                "*Features:*\n"
                "• Priority\\-based race organization\n"
                "• Target time tracking\n"
                "• Location and notes storage\n"
                "• Race\\-specific training adaptation\n\n"
                "*Tips:*\n"
                "• Set race priorities \\(A/B/C\\)\n"
                "• Include target times\n"
                "• Keep race details updated"
            ),
            "other": (
                "ℹ️ *Additional Features*\n\n"
                "*Commands:*\n"
                "• `/help` \\- Show help menu\n"
                "• `/roadmap` \\- View roadmap\n\n"
                "*Tips:*\n"
                "• Use command shortcuts for quick access\n"
                "• Check roadmap for upcoming features\n"
                "• Use inline buttons for easy navigation\n\n"
                "*Support:*\n"
                "• Error messages include helpful tips\n"
                "• Clear feedback for all actions\n"
                "• Regular updates and improvements"
            )
        }
        
        roadmap_messages = {
            "features": (
                "📱 *Upcoming Features Details*\n\n"
                "*Q1 2024:*\n"
                "• Advanced training load tracking\n"
                "• AI\\-powered recovery guidance\n"
                "• Performance trend analysis\n"
                "• Personalized training zones\n\n"
                "*Q2 2024:*\n"
                "• Group training support\n"
                "• Virtual training partners\n"
                "• Achievement sharing\n"
                "• Training plan marketplace\n\n"
                "*Future Considerations:*\n"
                "• Live workout guidance\n"
                "• Virtual coaching sessions\n"
                "• Training camp organization"
            ),
            "technical": (
                "🔧 *Technical Improvements*\n\n"
                "*Performance:*\n"
                "• Faster data processing\n"
                "• Improved response times\n"
                "• Better data compression\n"
                "• Enhanced caching\n\n"
                "*Infrastructure:*\n"
                "• Scalable architecture\n"
                "• Better error handling\n"
                "• Automated testing\n"
                "• Continuous deployment\n\n"
                "*Security:*\n"
                "• Enhanced encryption\n"
                "• Regular security audits\n"
                "• Privacy improvements"
            ),
            "longterm": (
                "🎯 *Long Term Vision*\n\n"
                "*Training Evolution:*\n"
                "• Advanced AI coaching\n"
                "• Predictive analytics\n"
                "• Injury prevention\n"
                "• Recovery optimization\n\n"
                "*Community:*\n"
                "• Global training network\n"
                "• Coach collaboration\n"
                "• Knowledge sharing\n"
                "• Event organization\n\n"
                "*Integration:*\n"
                "• Multiple platforms\n"
                "• Smart equipment\n"
                "• Health services"
            ),
            "updates": (
                "📢 *Recent & Upcoming Updates*\n\n"
                "*Just Released:*\n"
                "• Command shortcuts\n"
                "• Inline navigation\n"
                "• Enhanced help system\n"
                "• Better error handling\n\n"
                "*Coming Soon:*\n"
                "• Weekly progress reports\n"
                "• Custom notifications\n"
                "• Training summaries\n"
                "• Goal tracking\n\n"
                "*In Development:*\n"
                "• Mobile optimization\n"
                "• Data visualization\n"
                "• Export features"
            )
        }
        
        messages = help_messages if category_type == "help" else roadmap_messages
        if category in messages:
            await query.message.reply_text(
                messages[category],
                parse_mode=ParseMode.MARKDOWN_V2
            )
            return
            
    handlers = {
        "login": start_login,
        "generate": generate,
        "workout": workout,
        "races": races,
        "help": help,
        "roadmap": roadmap
    }
    
    handler = handlers.get(query.data)
    if handler:
        try:
            await query.message.reply_text(
                escape_markdown("🔄 Processing your request..."),
                parse_mode=ParseMode.MARKDOWN_V2
            )
            # Pass the original update - handlers now use message = update.message or update.callback_query.message
            await handler(update, context)
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error in button handler: {error_msg}")
            await query.message.reply_text(
                escape_markdown("❌ Something went wrong. Please try using the command directly."),
                parse_mode=ParseMode.MARKDOWN_V2
            )
    else:
        logger.error(f"No handler found for callback data: {query.data}")
        await query.message.reply_text(
            escape_markdown("❌ Something went wrong. Please try using the command directly."),
            parse_mode=ParseMode.MARKDOWN_V2
        )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /start command."""
    message = update.message or update.callback_query.message
    if not update.effective_user:
        logger.error("Update is missing effective_user")
        await message.reply_text(
            "❌ An error occurred. Unable to identify user.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return

    user_name = update.effective_user.first_name
    keyboard = [
        [
            InlineKeyboardButton("🔐 Login", callback_data="login"),
            InlineKeyboardButton("📊 Generate Insights", callback_data="generate")
        ],
        [
            InlineKeyboardButton("🏋️ Get Workout", callback_data="workout"),
            InlineKeyboardButton("🏃 Race Calendar", callback_data="races")
        ],
        [
            InlineKeyboardButton("ℹ️ Help", callback_data="help"),
            InlineKeyboardButton("🗺️ Roadmap", callback_data="roadmap")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await message.reply_text(
        escape_markdown(f"Hey {user_name}! 🏃‍♂️ Welcome to your AI Training Assistant!\n\n") +
        "*Quick Commands:*\n\n" +
        "🔐 *Authentication:*\n" +
        "• `/login` \\- Connect Garmin account\n\n" +
        "📊 *Training:*\n" +
        "• `/generate` \\- Get AI training insights\n" +
        "• `/workout` \\- Get workout suggestions\n\n" +
        "🏃‍♂️ *Races:*\n" +
        "• `/races` \\- View race calendar\n" +
        "• `/addrace` \\- Add competition\n" +
        "• `/editrace` \\- Edit competition\n" +
        "• `/delrace` \\- Remove competition\n\n" +
        "ℹ️ *Help & Info:*\n" +
        "• `/help` \\- Detailed help\n" +
        "• `/roadmap` \\- Future features\n\n" +
        "🔒 *Security:*\n" +
        "• End\\-to\\-end encrypted\n" +
        "• Secure credential storage\n" +
        "• Privacy\\-focused design\n\n" +
        "Use the buttons below for quick access or type a command to get started\\! 🚀",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN_V2
    )


async def help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /help command."""
    message = update.message or update.callback_query.message
    keyboard = [
        [
            InlineKeyboardButton("🔐 Authentication", callback_data="help_auth"),
            InlineKeyboardButton("📊 Training", callback_data="help_training")
        ],
        [
            InlineKeyboardButton("🏃 Races", callback_data="help_races"),
            InlineKeyboardButton("ℹ️ Other", callback_data="help_other")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await message.reply_text(
        "🤖 *Command Reference*\n\n" +
        "🔐 *Authentication Commands:*\n" +
        "• `/login` \\- Connect Garmin account\n" +
        "• `/clear_credentials` \\- Remove credentials\n\n" +
        "📊 *Training Commands:*\n" +
        "• `/generate` \\- Get AI training insights\n" +
        "• `/workout` \\- Get workout suggestions\n\n" +
        "🏃‍♂️ *Race Commands:*\n" +
        "• `/races` \\- View race calendar\n" +
        "• `/addrace` \\- Add competition\n" +
        "• `/editrace` \\- Edit competition\n" +
        "• `/delrace` \\- Remove competition\n\n" +
        "ℹ️ *Help & Info:*\n" +
        "• `/help` \\- Show this help\n" +
        "• `/roadmap` \\- View roadmap\n\n" +
        "🔒 *Security Features:*\n" +
        "• End\\-to\\-end encrypted communication\n" +
        "• Secure credential storage with encryption\n" +
        "• Privacy\\-focused design\n" +
        "• Regular security updates\n\n" +
        "Select a category below for detailed help:",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=reply_markup
    )

async def roadmap(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /roadmap command."""
    message = update.message or update.callback_query.message
    keyboard = [
        [
            InlineKeyboardButton("📱 Features", callback_data="roadmap_features"),
            InlineKeyboardButton("🔧 Technical", callback_data="roadmap_technical")
        ],
        [
            InlineKeyboardButton("🎯 Long Term", callback_data="roadmap_longterm"),
            InlineKeyboardButton("📢 Updates", callback_data="roadmap_updates")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await message.reply_text(
        "🗺️ *Development Roadmap*\n\n" +
        "*Upcoming Features:*\n\n" +
        "1️⃣ *Advanced Training Analysis* \\(Q1 2024\\)\n" +
        "• Smart training load management\n" +
        "• Recovery optimization\n" +
        "• Performance predictions\n\n" +
        "2️⃣ *Enhanced AI Coaching* \\(Q1 2024\\)\n" +
        "• Personalized training plans\n" +
        "• Real\\-time workout adjustments\n" +
        "• Race\\-specific preparation\n\n" +
        "3️⃣ *Social Features* \\(Q2 2024\\)\n" +
        "• Training groups\n" +
        "• Progress sharing\n" +
        "• Community challenges\n\n" +
        "4️⃣ *Technical Improvements*\n" +
        "• Enhanced data analytics\n" +
        "• Faster response times\n" +
        "• Additional integrations\n\n" +
        "Select a category below for more details:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN_V2
    )

async def clear_credentials(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /clear_credentials command."""
    user_id = update.effective_user.id
    message = update.message or update.callback_query.message
    cred_manager = SecureCredentialManager(user_id)
    
    if cred_manager.clear():
        await message.reply_text(
            "✅ Your stored credentials have been cleared\\.\n" +
            "Use `/login` to set up new credentials\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
    else:
        await message.reply_text(
            "❌ Failed to clear credentials\\. Please try again or contact support\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )

async def races(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /races command - List upcoming competitions."""
    user_id = update.effective_user.id  # This works for both message and callback
    message = update.message or update.callback_query.message
    comp_manager = SecureCompetitionManager(user_id)
    
    try:
        upcoming = comp_manager.get_upcoming_competitions()
        
        if not upcoming:
            await message.reply_text(
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
        
        await message.reply_text(
            response,
            parse_mode=ParseMode.MARKDOWN_V2
        )
        
    except Exception:
        await message.reply_text(
            "❌ Failed to retrieve race calendar\\. Please try again\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )

async def delrace(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /delrace command - Remove a competition."""
    message = update.message or update.callback_query.message
    message_text = message.text.strip() if message else ""
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
            await message.reply_text(
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
        
        await message.reply_text(
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
                response = escape_markdown("❌ No race found on that date.\n\n") + "*Available Races:*\n"
                for race in upcoming:
                    date_str = race.date.strftime("%Y-%m-%d")
                    response += (
                        f"• {escape_markdown(date_str)} \\- "
                        f"{escape_markdown(race.name)} "
                        f"\\({escape_markdown(race.race_type)}\\)\n"
                    )
            else:
                response = escape_markdown("❌ No races found in your calendar.\n\n") + escape_markdown("Use /addrace to add a competition!")
                
            await message.reply_text(
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
            
            await message.reply_text(
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
            await message.reply_text(
                "❌ Failed to delete race\\. Please try again\\.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            
    except ValueError as ve:
        logger.error(f"Invalid date format: {str(ve)}")
        await message.reply_text(
            "❌ Invalid date format\\. Please use YYYY\\-MM\\-DD\n" +
            "Example: `2024\\-06\\-30`",
            parse_mode=ParseMode.MARKDOWN_V2
        )
    except StorageError as se:
        logger.error(f"Storage error in delrace: {str(se)}")
        await message.reply_text(
            "❌ Failed to delete race due to storage error\\. Please try again\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
    except Exception as e:
        logger.error(f"Unexpected error in delrace: {str(e)}")
        await message.reply_text(
            "❌ Failed to delete race\\. Please try again\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
