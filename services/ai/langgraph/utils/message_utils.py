import logging

logger = logging.getLogger(__name__)


def extract_text_content(response) -> str:
    if hasattr(response, 'content_blocks'):
        try:
            blocks = response.content_blocks
            text_parts = [b["text"] for b in blocks if b.get("type") == "text" and "text" in b]
            if text_parts:
                return "".join(text_parts)
        except Exception as e:
            logger.debug(f"Failed to extract from content_blocks: {e}")
    
    content = response.content if hasattr(response, 'content') else response
    
    if isinstance(content, str):
        return content
    
    if isinstance(content, list):
        text_item = next(
            (item["text"] for item in content
             if isinstance(item, dict) and item.get("type") == "text" and "text" in item),
            None
        )
        if text_item:
            return text_item
        
        text_item = next(
            (item["text"] for item in content
             if isinstance(item, dict) and "text" in item),
            None
        )
        if text_item:
            return text_item
    
    return str(content)