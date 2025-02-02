"""Message formatting utilities for the Telegram bot."""

from chatgpt_md_converter import telegram_format
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

def format_and_send_report(report_text: str) -> tuple[list, ParseMode]:
    """
    Format and split report into chunks while preserving logical blocks.
    Converts Markdown from AI agents to HTML for Telegram.
    
    Args:
        report_text: The report text to format and split
        
    Returns:
        tuple: (List of chunks ready to be sent via Telegram, ParseMode to use)
    """
    max_length = 4000  # Telegram character limit
    chunks = []
    current_chunk = ""
    
    # Split on double newlines to preserve logical blocks
    blocks = report_text.split('\n\n')
    
    for block in blocks:
        # Convert markdown to HTML using chatgpt_md_converter
        formatted_block = telegram_format(block)
        
        # If adding this block would exceed limit, start new chunk
        if len(current_chunk) + len(formatted_block) + 2 > max_length:
            chunks.append(current_chunk)
            current_chunk = formatted_block
        else:
            if current_chunk:
                current_chunk += '\n\n'
            current_chunk += formatted_block
    
    # Add final chunk if any
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks, ParseMode.HTML
