import logging

from telegram.ext import ApplicationBuilder, CallbackQueryHandler, CommandHandler

from bot.handlers.coach_handlers import coach_handler
from bot.handlers.command_handlers import (
    clear_credentials,
    delrace,
    handle_button,
    help,
    races,
    roadmap,
    start,
)
from bot.handlers.conversation_handlers import (
    add_race_handler,
    edit_race_handler,
    login_handler,
    start_add_race,
    start_edit_race,
)
from bot.handlers.error_handlers import error_handler
from core.config import get_config

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)


class TelegramBot:

    def __init__(self):
        self.config = get_config()
        self.app = None

    def setup(self):
        # Initialize application with increased timeouts
        self.app = (
            ApplicationBuilder()
            .token(self.config.bot_token)
            .read_timeout(300)
            .write_timeout(300)
            .build()
        )

        # Store API key in bot_data for handlers to access
        self.app.bot_data['anthropic_api_key'] = self.config.anthropic_api_key

        # Add conversation handlers first
        self.app.add_handler(login_handler)
        self.app.add_handler(add_race_handler)
        self.app.add_handler(edit_race_handler)
        self.app.add_handler(coach_handler)

        # Add command handlers
        self.app.add_handler(CommandHandler("start", start))
        self.app.add_handler(CommandHandler("races", races))
        self.app.add_handler(CommandHandler("addrace", start_add_race))
        self.app.add_handler(CommandHandler("editrace", start_edit_race))
        self.app.add_handler(CommandHandler("delrace", delrace))
        self.app.add_handler(CommandHandler("help", help))
        self.app.add_handler(CommandHandler("roadmap", roadmap))
        self.app.add_handler(CommandHandler("clear_credentials", clear_credentials))

        # Add callback query handler for inline keyboard
        self.app.add_handler(CallbackQueryHandler(handle_button))

        # Error handler
        self.app.add_error_handler(error_handler)

        logger.info("Bot setup completed")

    def run(self):
        if not self.app:
            raise RuntimeError("Bot not set up. Call setup() first.")

        logger.info("Starting bot...")
        self.app.run_polling()


def create_bot():
    bot = TelegramBot()
    bot.setup()
    return bot
