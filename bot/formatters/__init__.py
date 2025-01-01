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
    # Escape all special characters including asterisks
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
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
        lines = block.split('\n')
        formatted_lines = []
        
        for line in lines:
            # Handle bold text (already marked with *asterisks*)
            parts = line.split('*')
            formatted_line = ""
            for i, part in enumerate(parts):
                if i % 2 == 0:  # Regular text
                    formatted_line += escape_markdown(part)
                else:  # Text between asterisks (bold)
                    formatted_line += f"*{escape_markdown(part)}*"
            formatted_lines.append(formatted_line)
        
        formatted_block = '\n'.join(formatted_lines)
        
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
    
    return chunks
