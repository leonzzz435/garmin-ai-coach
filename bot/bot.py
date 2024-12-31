"""Main bot module for initializing and running the Telegram bot."""

import logging
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    filters
)

from core.config import get_config
from bot.handlers.command_handlers import (
    start,
    help,
    roadmap,
    clear_credentials
)
from bot.handlers.conversation_handlers import (
    start_login,
    process_email,
    process_password,
    cancel,
    EXPECTING_EMAIL,
    EXPECTING_PASSWORD
)
from bot.handlers.data_handlers import (
    generate,
    workout
)
from bot.handlers.error_handlers import error_handler

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TelegramBot:
    """Main bot class that handles initialization and setup."""
    
    def __init__(self):
        """Initialize the bot with configuration."""
        self.config = get_config()
        self.app = None
    
    def setup(self):
        """Set up the bot with all handlers."""
        # Initialize application
        self.app = ApplicationBuilder().token(self.config.bot_token).build()
        
        # Store API key in bot_data for handlers to access
        self.app.bot_data['anthropic_api_key'] = self.config.anthropic_api_key
        
        # Set up conversation handler for login
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
        
        # Add handlers
        self.app.add_handler(login_handler)  # Must be added first
        self.app.add_handler(CommandHandler("start", start))
        self.app.add_handler(CommandHandler("generate", generate))
        self.app.add_handler(CommandHandler("roadmap", roadmap))
        self.app.add_handler(CommandHandler("help", help))
        self.app.add_handler(CommandHandler("clear_credentials", clear_credentials))
        self.app.add_handler(CommandHandler("workout", workout))
        
        # Error handler
        self.app.add_error_handler(error_handler)
        
        logger.info("Bot setup completed")
    
    def run(self):
        """Start the bot."""
        if not self.app:
            raise RuntimeError("Bot not set up. Call setup() first.")
        
        logger.info("Starting bot...")
        self.app.run_polling()

def create_bot():
    """Create and configure a new bot instance."""
    bot = TelegramBot()
    bot.setup()
    return bot
