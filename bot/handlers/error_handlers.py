
import logging
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from bot.formatters import escape_markdown

# Configure logging
logger = logging.getLogger(__name__)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(f"Update {update} caused error {context.error}")
    
    if update:
        error_message = escape_markdown(
            "❌ Something went wrong\\. Please try again\\."
        )
        
        try:
            if update.callback_query:
                await update.callback_query.message.reply_text(
                    error_message,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            elif update.message:
                await update.message.reply_text(
                    error_message,
                    parse_mode=ParseMode.MARKDOWN_V2
                )
        except Exception as e:
            logger.error(f"Failed to send error message: {str(e)}")
