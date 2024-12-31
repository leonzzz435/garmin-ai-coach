"""Error handlers for the Telegram bot."""

import logging
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.formatters import escape_markdown

# Configure logging
logger = logging.getLogger(__name__)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors occurring in the dispatcher."""
    logger.error(f"Update {update} caused error {context.error}")
    if update:
        error_message = escape_markdown(
            f"⚠️ Something unexpected happened: {context.error}\n"
            "No worries - Zett is working on that already (maybe 😁)"
        )
        await update.message.reply_text(
            error_message,
            parse_mode=ParseMode.MARKDOWN_V2
        )
