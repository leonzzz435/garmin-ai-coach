def escape_markdown(text: str) -> str:
    # First escape the backslash itself
    text = text.replace('\\', '\\\\')
    # Escape all special characters including asterisks
    special_chars = [
        '_',
        '*',
        '[',
        ']',
        '(',
        ')',
        '~',
        '`',
        '>',
        '#',
        '+',
        '-',
        '=',
        '|',
        '{',
        '}',
        '.',
        '!',
    ]
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text
