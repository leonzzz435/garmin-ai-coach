"""AI client module for managing Anthropic API interactions."""

import logging
from typing import Optional
import anthropic
from core.config import get_config

logger = logging.getLogger(__name__)

class AIClientError(Exception):
    """Base exception for AI client errors."""
    pass

class ConnectionError(AIClientError):
    """Raised when there are issues connecting to the AI service."""
    pass

class APIKeyError(AIClientError):
    """Raised when there are issues with the API key."""
    pass

def create_ai_client() -> anthropic.Anthropic:
    """
    Create and configure the Anthropic client with error handling.
    
    Returns:
        anthropic.Anthropic: Configured Anthropic client instance
        
    Raises:
        APIKeyError: If the API key is missing or invalid
        ConnectionError: If there are issues connecting to the service
    """
    try:
        config = get_config()
        if not config.anthropic_api_key:
            raise APIKeyError("Anthropic API key is missing")
            
        client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        
        # Test connection by making a minimal API call
        try:
            client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1,
                messages=[{
                    "role": "user",
                    "content": "test"
                }]
            )
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Anthropic API: {str(e)}")
            
        logger.info("Successfully initialized Anthropic client")
        return client
        
    except Exception as e:
        logger.error(f"Error initializing Anthropic client: {str(e)}")
        raise AIClientError(f"Failed to initialize AI client: {str(e)}")
