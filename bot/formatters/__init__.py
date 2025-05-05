"""Message formatting utilities for the Telegram bot."""

from telegram.constants import ParseMode

def escape_markdown(text: str) -> str:
    """
    Escapes special characters for Telegram MarkdownV2.
    
    Args:
        text: The text to escape
        
    Returns:
        str: The escaped text safe for MarkdownV2 parsing
    """
    # First escape the backslash itself
    text = text.replace('\\', '\\\\')
    # Escape all special characters including asterisks
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text
