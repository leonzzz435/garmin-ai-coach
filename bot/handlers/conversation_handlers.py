"""Conversation handlers for the Telegram bot."""

import logging
from datetime import date
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.constants import ParseMode
from bot.formatters import escape_markdown
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters
)

from core.security import SecureCredentialManager, SecureCompetitionManager
from services.garmin import TriathlonCoachDataExtractor
from services.garmin.competition_models import Competition, RacePriority

# Configure logging
logger = logging.getLogger(__name__)

# Define conversation states
# Login states
EXPECTING_EMAIL = 1
EXPECTING_PASSWORD = 2

# Add race states
RACE_NAME = 10
RACE_DATE = 11
RACE_TYPE = 12
RACE_PRIORITY = 13
RACE_TARGET = 14
RACE_LOCATION = 15
RACE_NOTES = 16

# Edit race states
EDIT_DATE = 20
EDIT_FIELD = 21
EDIT_VALUE = 22

# Initialize global variables
user_data = {}  # Structure: {user_id: {'temp_email': str, 'race_data': dict}}

# Keyboard layouts
PRIORITY_KEYBOARD = [[p.value] for p in RacePriority]
EDIT_FIELDS_KEYBOARD = [
    ['Name'], ['Date'], ['Type'], ['Priority'],
    ['Target Time'], ['Location'], ['Notes'],
    ['Done']
]

# Example messages
RACE_TYPE_EXAMPLES = "Examples: 5k, Half Marathon, Sprint Tri, Olympic Distance, 70.3"
TARGET_TIME_EXAMPLES = "Examples: sub 3, 2:30 hrs, 45 minutes, around 5 hours"
LOCATION_EXAMPLES = "Examples: Berlin, Central Park NYC, Lake Placid NY"

async def start_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the login process."""
    user_id = update.effective_user.id
    # Check if user already has stored credentials
    cred_manager = SecureCredentialManager(user_id)
    if cred_manager.has_stored_credentials():
        await update.message.reply_text(
            "⚠️ You already have stored credentials\\. Options:\n\n" +
            "1\\. Continue with stored credentials: Use `/generate` or `/workout`\n" +
            "2\\. Clear stored credentials: `/clear_credentials`\n" +
            "3\\. Start fresh: Clear credentials first, then use `/login`",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return ConversationHandler.END

    # Initialize user data
    user_data[user_id] = {}

    # Ask for email first
    await update.message.reply_text(
        "Please enter your Garmin email address:",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    return EXPECTING_EMAIL

async def process_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process the email input and ask for password."""
    user_id = update.effective_user.id
    email = update.message.text.strip()
    
    # Store email temporarily for the login process
    user_data[user_id]["temp_email"] = email
    
    # Ask for password
    await update.message.reply_text(
        "Great\\! Now please enter your password:",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    return EXPECTING_PASSWORD

async def process_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process the password and complete login."""
    user_id = update.effective_user.id
    password = update.message.text.strip()
    email = user_data[user_id].get("temp_email")
    # Delete the message containing the password immediately
    await update.message.delete()
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="🔐 Testing connection to Garmin\\.\\.\\.",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    
    try:
        # Test connection with Garmin
        extractor = TriathlonCoachDataExtractor(email, password)
        
        # Store credentials securely
        cred_manager = SecureCredentialManager(user_id)
        if cred_manager.store_credentials(email, password):
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="✅ Connection successful\\!\n" +
                    "🔒 Credentials securely stored\\.\n" +
                    "Use /generate for insights or /workout for training suggestions\\! 🚀",
                parse_mode=ParseMode.MARKDOWN_V2
            )
        else:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ Connection successful but failed to store credentials\\.\n" +
                    "Please try again or contact support\\.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
    except Exception as e:
        logger.error(f"Connection test error: {str(e)}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Connection failed\\. Please check your credentials and try again\\.\n" +
                "Your password was not stored\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel any conversation."""
    await update.message.reply_text(
        "Operation cancelled\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

# Add Race Conversation Handlers
async def start_add_race(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the add race process."""
    user_id = update.effective_user.id
    user_data[user_id] = {"race_data": {}}
    
    await update.message.reply_text(
        "Let's add a new race to your calendar\\! 🏃‍♂️\n\n" +
        "First, what's the name of the race\\?",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    return RACE_NAME

async def process_race_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process race name and ask for date."""
    user_id = update.effective_user.id
    user_data[user_id]["race_data"]["name"] = update.message.text.strip()
    
    await update.message.reply_text(
        "When is the race\\? Please use format YYYY\\-MM\\-DD\n" +
        "Example: `2024\\-06\\-30`\n" +
        "Use /cancel to cancel",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    return RACE_DATE

async def process_race_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process race date and ask for type."""
    try:
        user_id = update.effective_user.id
        date_input = update.message.text.strip().replace(".", "-")
        race_date = date.fromisoformat(date_input)
        user_data[user_id]["race_data"]["date"] = race_date
        
        # Send next message without Markdown formatting
        await update.message.reply_text(
            f"What type of race is it?\n\n{RACE_TYPE_EXAMPLES}\n\nUse /cancel to cancel"
        )
        return RACE_TYPE
        
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid date format\\. Please use YYYY\\-MM\\-DD\n" +
            "Example: `2024\\-06\\-30`",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return RACE_DATE

async def process_race_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process race type and ask for priority."""
    user_id = update.effective_user.id
    race_type = update.message.text.strip()
    
    user_data[user_id]["race_data"]["race_type"] = race_type
    
    reply_markup = ReplyKeyboardMarkup(
        PRIORITY_KEYBOARD,
        one_time_keyboard=True,
        resize_keyboard=True
    )
    
    await update.message.reply_text(
        "What's the priority of this race?\n\n" +
        "A - Main season goal\n" +
        "B - Important but not primary\n" +
        "C - Training race or minor event",
        reply_markup=reply_markup
    )
    return RACE_PRIORITY

async def process_race_priority(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process race priority and ask for target time."""
    user_id = update.effective_user.id
    priority = update.message.text.strip()
    
    try:
        user_data[user_id]["race_data"]["priority"] = RacePriority(priority)
        
        await update.message.reply_text(
            "Do you have a target time? (optional)\n\n" +
            f"{TARGET_TIME_EXAMPLES}\n\n" +
            "Or press /skip to skip",
            reply_markup=ReplyKeyboardRemove()
        )
        return RACE_TARGET
        
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid priority\\. Please select A, B, or C\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return RACE_PRIORITY

async def process_race_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process target time and ask for location."""
    user_id = update.effective_user.id
    if update.message.text != "/skip":
        user_data[user_id]["race_data"]["target_time"] = update.message.text.strip()
    
    await update.message.reply_text(
        "Where is the race?\n\n" +
        f"{LOCATION_EXAMPLES}\n\n" +
        "Use /skip to skip or /cancel to cancel"
    )
    return RACE_LOCATION

async def process_race_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process location and ask for notes."""
    user_id = update.effective_user.id
    if update.message.text != "/skip":
        user_data[user_id]["race_data"]["location"] = update.message.text.strip()
    
    await update.message.reply_text(
        "Any additional notes? (optional, /skip to skip)"
    )
    return RACE_NOTES

async def process_race_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process notes and save the race."""
    user_id = update.effective_user.id
    if update.message.text != "/skip":
        user_data[user_id]["race_data"]["notes"] = update.message.text.strip()
    
    try:
        race_data = user_data[user_id]["race_data"]
        competition = Competition(
            name=race_data["name"],
            date=race_data["date"],
            race_type=race_data["race_type"],
            priority=race_data["priority"],
            target_time=race_data.get("target_time"),
            location=race_data.get("location"),
            notes=race_data.get("notes"),
            completed=False
        )
        
        comp_manager = SecureCompetitionManager(user_id)
        comp_manager.add_competition(competition)
        
        await update.message.reply_text(
            "✅ Race successfully added to your calendar\\!\n\n" +
            "Use `/races` to view your race calendar\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        
    except Exception as e:
        logger.error(f"Failed to save race: {str(e)}")
        await update.message.reply_text(
            "❌ Failed to save race\\. Please try again\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
    
    return ConversationHandler.END

# Edit Race Conversation Handlers
async def start_edit_race(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start the edit race process."""
    await update.message.reply_text(
        "What's the date of the race you want to edit\\? \\(YYYY\\-MM\\-DD\\)\n" +
        "Example: `2024\\-06\\-30`",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    return EDIT_DATE

async def process_edit_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process the date and show edit options."""
    try:
        date_input = update.message.text.strip().replace(".", "-")
        race_date = date.fromisoformat(date_input)
        user_id = update.effective_user.id
        comp_manager = SecureCompetitionManager(user_id)
        competition = comp_manager.get_competition(race_date)
        
        if not competition:
            await update.message.reply_text(
                "❌ No race found on that date\\.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            return ConversationHandler.END
            
        user_data[user_id] = {
            "edit_date": race_date,
            "current_race": competition
        }
        
        reply_markup = ReplyKeyboardMarkup(
            EDIT_FIELDS_KEYBOARD,
            one_time_keyboard=True,
            resize_keyboard=True
        )
        
        await update.message.reply_text(
            "*Current Race Details:*\n\n" +
            f"*Name:* {escape_markdown(competition.name)}\n" +
            f"*Date:* {escape_markdown(competition.date.isoformat())}\n" +
            f"*Type:* {escape_markdown(competition.race_type)}\n" +
            f"*Priority:* {escape_markdown(competition.priority.value)}\n" +
            f"*Target Time:* {escape_markdown(competition.target_time or 'Not set')}\n" +
            f"*Location:* {escape_markdown(competition.location or 'Not set')}\n" +
            f"*Notes:* {escape_markdown(competition.notes or 'Not set')}\n\n" +
            "What would you like to edit\\?",
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=reply_markup
        )
        return EDIT_FIELD
        
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid date format\\. Please use YYYY\\-MM\\-DD\n" +
            "Example: `2024\\-06\\-30`",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return EDIT_DATE

async def process_edit_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process the field selection and ask for new value."""
    field = update.message.text.strip()
    user_id = update.effective_user.id
    
    if field == "Done":
        # Get the current race details for the final summary
        current_race = user_data[user_id]["current_race"]
        
        # Create a summary message
        summary = (
            "✅ Race update completed\\!\n\n"
            "*Final Race Details:*\n"
            f"• *Name:* {escape_markdown(current_race.name)}\n"
            f"• *Date:* {escape_markdown(current_race.date.isoformat())}\n"
            f"• *Type:* {escape_markdown(current_race.race_type)}\n"
            f"• *Priority:* {escape_markdown(current_race.priority.value)}\n"
            f"• *Target Time:* {escape_markdown(current_race.target_time or 'Not set')}\n"
            f"• *Location:* {escape_markdown(current_race.location or 'Not set')}\n"
            f"• *Notes:* {escape_markdown(current_race.notes or 'Not set')}\n\n"
            "Use `/races` to view your race calendar\\!"
        )
        
        await update.message.reply_text(
            summary,
            parse_mode=ParseMode.MARKDOWN_V2,
            reply_markup=ReplyKeyboardRemove()
        )
        
        # Clean up user data
        if user_id in user_data:
            del user_data[user_id]
            
        return ConversationHandler.END
        
    user_data[user_id]["edit_field"] = field.lower()
    
    if field == "Type":
        await update.message.reply_text(
            f"Enter new race type:\n\n{RACE_TYPE_EXAMPLES}\n\nUse /cancel to cancel"
        )
        return EDIT_VALUE
    elif field == "Target Time":
        await update.message.reply_text(
            f"Enter new target time:\n\n{TARGET_TIME_EXAMPLES}\n\nOr /skip to clear"
        )
        return EDIT_VALUE
    elif field == "Location":
        await update.message.reply_text(
            f"Enter new location:\n\n{LOCATION_EXAMPLES}\n\nOr /skip to clear"
        )
        return EDIT_VALUE
    elif field == "Notes":
        await update.message.reply_text(
            "Enter new notes or /skip to clear"
        )
        return EDIT_VALUE
    elif field == "Priority":
        reply_markup = ReplyKeyboardMarkup(
            PRIORITY_KEYBOARD,
            one_time_keyboard=True,
            resize_keyboard=True
        )
    else:
        reply_markup = ReplyKeyboardRemove()
    
    await update.message.reply_text(
        f"Enter new value for {field}:",
        reply_markup=reply_markup
    )
    return EDIT_VALUE

async def process_edit_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process the new value and update the race."""
    user_id = update.effective_user.id
    field = user_data[user_id]["edit_field"]
    value = update.message.text.strip()
    current_race = user_data[user_id]["current_race"]
    
    try:
        # Create a new competition object with updated field
        updated_data = {
            "name": current_race.name,
            "date": current_race.date,
            "race_type": current_race.race_type,
            "priority": current_race.priority,
            "target_time": current_race.target_time,
            "location": current_race.location,
            "notes": current_race.notes,
            "completed": current_race.completed
        }
        
        if field == "name":
            updated_data["name"] = value
        elif field == "date":
            updated_data["date"] = date.fromisoformat(value)
        elif field == "type":
            updated_data["race_type"] = value
        elif field == "priority":
            updated_data["priority"] = RacePriority(value)
        elif field == "target time":
            if value == "/skip":
                updated_data["target_time"] = None
            else:
                updated_data["target_time"] = value
        elif field == "location":
            if value == "/skip":
                updated_data["location"] = None
            else:
                updated_data["location"] = value
        elif field == "notes":
            if value == "/skip":
                updated_data["notes"] = None
            else:
                updated_data["notes"] = value
            
        updated_race = Competition(**updated_data)
        comp_manager = SecureCompetitionManager(user_id)
        
        if comp_manager.update_competition(user_data[user_id]["edit_date"], updated_race):
            user_data[user_id]["current_race"] = updated_race
            if field == "date":
                user_data[user_id]["edit_date"] = updated_race.date
                
            # Show updated race details
            details_message = (
                "✅ Update successful\\!\n\n"
                "*Current Race Details:*\n"
                f"• *Name:* {escape_markdown(updated_race.name)}\n"
                f"• *Date:* {escape_markdown(updated_race.date.isoformat())}\n"
                f"• *Type:* {escape_markdown(updated_race.race_type)}\n"
                f"• *Priority:* {escape_markdown(updated_race.priority.value)}\n"
                f"• *Target Time:* {escape_markdown(updated_race.target_time or 'Not set')}\n"
                f"• *Location:* {escape_markdown(updated_race.location or 'Not set')}\n"
                f"• *Notes:* {escape_markdown(updated_race.notes or 'Not set')}\n\n"
                "Select another field to edit or choose *Done* to finish\\."
            )
            
            reply_markup = ReplyKeyboardMarkup(
                EDIT_FIELDS_KEYBOARD,
                one_time_keyboard=True,
                resize_keyboard=True
            )
            
            await update.message.reply_text(
                details_message,
                parse_mode=ParseMode.MARKDOWN_V2,
                reply_markup=reply_markup
            )
            return EDIT_FIELD
            
    except ValueError as e:
        await update.message.reply_text(
            f"❌ Invalid value\\. {str(e)}",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return EDIT_VALUE
    except Exception as e:
        logger.error(f"Failed to update race: {str(e)}")
        await update.message.reply_text(
            "❌ Failed to update race\\. Please try again\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return ConversationHandler.END

# Create conversation handlers
login_handler = ConversationHandler(
    entry_points=[CommandHandler("login", start_login)],
    states={
        EXPECTING_EMAIL: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                process_email
            )
        ],
        EXPECTING_PASSWORD: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                process_password
            )
        ]
    },
    fallbacks=[CommandHandler("cancel", cancel)]
)

add_race_handler = ConversationHandler(
    entry_points=[CommandHandler("addrace", start_add_race)],
    states={
        RACE_NAME: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                process_race_name
            )
        ],
        RACE_DATE: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                process_race_date
            )
        ],
        RACE_TYPE: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                process_race_type
            )
        ],
        RACE_PRIORITY: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                process_race_priority
            )
        ],
        RACE_TARGET: [
            MessageHandler(
                (filters.TEXT & ~filters.COMMAND) | filters.Regex("^/skip$"),
                process_race_target
            )
        ],
        RACE_LOCATION: [
            MessageHandler(
                (filters.TEXT & ~filters.COMMAND) | filters.Regex("^/skip$"),
                process_race_location
            )
        ],
        RACE_NOTES: [
            MessageHandler(
                (filters.TEXT & ~filters.COMMAND) | filters.Regex("^/skip$"),
                process_race_notes
            )
        ]
    },
    fallbacks=[CommandHandler("cancel", cancel)]
)

edit_race_handler = ConversationHandler(
    entry_points=[CommandHandler("editrace", start_edit_race)],
    states={
        EDIT_DATE: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                process_edit_date
            )
        ],
        EDIT_FIELD: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                process_edit_field
            )
        ],
        EDIT_VALUE: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                process_edit_value
            )
        ]
    },
    fallbacks=[CommandHandler("cancel", cancel)]
)
