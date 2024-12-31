"""Message formatting utilities for the Telegram bot."""

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
    # Then escape all other special characters except asterisks (used for bold)
    special_chars = ['_', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

def format_and_send_report(report_text: str) -> list:
    """
    Format and split report into chunks while escaping special characters.
    
    Args:
        report_text: The report text to format and split
        
    Returns:
        list: List of chunks ready to be sent via Telegram
    """
    max_length = 4000  # Telegram character limit
    escaped_text = escape_markdown(report_text)  # Escape MarkdownV2 characters
    return [escaped_text[i:i + max_length] for i in range(0, len(escaped_text), max_length)]
