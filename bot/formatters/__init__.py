"""Message formatting utilities for the Telegram bot."""

import re

def escape_markdown(text: str) -> str:
    """
    Escapes special characters for Telegram MarkdownV2 while preserving bold formatting.
    
    Args:
        text: The text to escape
        
    Returns:
        str: The escaped text safe for MarkdownV2 parsing
    """
    # Convert double asterisks to single for Telegram's format
    text = re.sub(r'\*\*(.*?)\*\*', r'*\1*', text)
    
    # Escape special characters except asterisks
    text = text.replace('\\', '\\\\')
    special_chars = ['_', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    
    return text

def format_and_send_report(report_text: str) -> list:
    """
    Format and split report into chunks at block boundaries (double newlines).
    
    Args:
        report_text: The report text to format and split
        
    Returns:
        list: List of chunks ready to be sent via Telegram
    """
    max_length = 4000  # Telegram character limit
    chunks = []
    current_chunk = ""
    
    # Split on double newlines
    blocks = report_text.split('\n\n')
    
    for block in blocks:
        # If block itself exceeds max_length, split it
        if len(block) > max_length:
            if current_chunk:
                chunks.append(escape_markdown(current_chunk))
                current_chunk = ""
            # Split long block at max_length
            chunks.extend([
                escape_markdown(block[i:i + max_length])
                for i in range(0, len(block), max_length)
            ])
            continue
            
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
