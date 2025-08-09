"""Main entry point for the Telegram bot application."""

import logging

import anthropic

from bot import create_bot
from core.config import get_config

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize the Anthropic Client for global use if needed
config = get_config()
client = anthropic.Anthropic(api_key=config.anthropic_api_key)


def main():
    """Main function to run the bot."""
    bot = create_bot()
    bot.run()


if __name__ == "__main__":
    main()
