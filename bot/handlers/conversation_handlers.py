"""Conversation handlers for the Telegram bot."""

import logging
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
)

from core.security import SecureCredentialManager
from services.garmin import TriathlonCoachDataExtractor

# Configure logging
logger = logging.getLogger(__name__)

# Define conversation states
EXPECTING_EMAIL = 1
EXPECTING_PASSWORD = 2

# Initialize global variables
user_data = {}  # Structure: {user_id: {'temp_email': str}}

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
    """Cancel the conversation."""
    await update.message.reply_text(
        "Login cancelled\\. Use /login to try again\\.",
        parse_mode=ParseMode.MARKDOWN_V2
    )
    return ConversationHandler.END

# Create the conversation handler
login_handler = ConversationHandler(
    entry_points=[],  # Will be set in bot.py
    states={
        EXPECTING_EMAIL: [],  # Will be set in bot.py
        EXPECTING_PASSWORD: []  # Will be set in bot.py
    },
    fallbacks=[]  # Will be set in bot.py
)
