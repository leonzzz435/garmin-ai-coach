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
    Format and split report into chunks while preserving logical blocks.
    
    Args:
        report_text: The report text to format and split
        
    Returns:
        list: List of chunks ready to be sent via Telegram
    """
    max_length = 4000  # Telegram character limit
    chunks = []
    current_chunk = ""
    
    # Split on double newlines to preserve logical blocks
    blocks = report_text.split('\n\n')
    
    for block in blocks:
        # If adding this block would exceed limit, start new chunk
        if len(current_chunk) + len(block) + 2 > max_length:
            chunks.append(escape_markdown(current_chunk))
            current_chunk = block
        else:
            if current_chunk:
                current_chunk += '\n\n'
            current_chunk += block
    
    # Add final chunk if any
    if current_chunk:
        chunks.append(escape_markdown(current_chunk))
    
    return chunks
