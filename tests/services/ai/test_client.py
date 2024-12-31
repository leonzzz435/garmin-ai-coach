import pytest
from unittest.mock import MagicMock, patch
import anthropic

from services.ai.client import (
    create_ai_client,
    AIClientError,
    ConnectionError,
    APIKeyError
)

@pytest.fixture
def mock_config():
    """Create a mock configuration."""
    config = MagicMock()
    config.anthropic_api_key = "test-api-key"
    return config

@pytest.fixture
def mock_anthropic_client():
    """Create a mock Anthropic client."""
    client = MagicMock()
    messages = MagicMock()
    messages.create.return_value = MagicMock()
    client.messages = messages
    return client

class TestAIClient:
    """Tests for AI client functionality."""

    def test_successful_client_creation(self, mock_config, mock_anthropic_client):
        """Test successful creation of Anthropic client."""
        with patch('services.ai.client.get_config', return_value=mock_config), \
             patch('services.ai.client.anthropic.Anthropic', return_value=mock_anthropic_client):
            
            client = create_ai_client()
            assert isinstance(client, MagicMock)  # In test, it's a mock
            
            # Verify the test connection was attempted
            client.messages.create.assert_called_once_with(
                model="claude-3-haiku-20240307",
                max_tokens=1,
                messages=[{
                    "role": "user",
                    "content": "test"
                }]
            )

    def test_missing_api_key(self, mock_config):
        """Test error handling when API key is missing."""
        mock_config.anthropic_api_key = None
        
        with patch('services.ai.client.get_config', return_value=mock_config):
            with pytest.raises(APIKeyError) as exc_info:
                create_ai_client()
            assert "API key is missing" in str(exc_info.value)

    def test_empty_api_key(self, mock_config):
        """Test error handling when API key is empty."""
        mock_config.anthropic_api_key = ""
        
        with patch('services.ai.client.get_config', return_value=mock_config):
            with pytest.raises(APIKeyError) as exc_info:
                create_ai_client()
            assert "API key is missing" in str(exc_info.value)

    def test_connection_error(self, mock_config):
        """Test error handling when connection fails."""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("Connection failed")
        
        with patch('services.ai.client.get_config', return_value=mock_config), \
             patch('services.ai.client.anthropic.Anthropic', return_value=mock_client):
            
            with pytest.raises(ConnectionError) as exc_info:
                create_ai_client()
            assert "Failed to connect to Anthropic API" in str(exc_info.value)

    def test_anthropic_client_error(self, mock_config):
        """Test error handling when Anthropic client creation fails."""
        with patch('services.ai.client.get_config', return_value=mock_config), \
             patch('services.ai.client.anthropic.Anthropic', side_effect=Exception("Invalid API key")):
            
            with pytest.raises(AIClientError) as exc_info:
                create_ai_client()
            assert "Failed to initialize AI client" in str(exc_info.value)

    def test_config_error(self):
        """Test error handling when config retrieval fails."""
        with patch('services.ai.client.get_config', side_effect=Exception("Config error")):
            with pytest.raises(AIClientError) as exc_info:
                create_ai_client()
            assert "Failed to initialize AI client" in str(exc_info.value)

    def test_anthropic_api_error(self, mock_config):
        """Test error handling for specific Anthropic API errors."""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = anthropic.APIError("API Error")
        
        with patch('services.ai.client.get_config', return_value=mock_config), \
             patch('services.ai.client.anthropic.Anthropic', return_value=mock_client):
            
            with pytest.raises(ConnectionError) as exc_info:
                create_ai_client()
            assert "Failed to connect to Anthropic API" in str(exc_info.value)

    def test_rate_limit_error(self, mock_config):
        """Test error handling for rate limit errors."""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = anthropic.RateLimitError("Rate limit exceeded")
        
        with patch('services.ai.client.get_config', return_value=mock_config), \
             patch('services.ai.client.anthropic.Anthropic', return_value=mock_client):
            
            with pytest.raises(ConnectionError) as exc_info:
                create_ai_client()
            assert "Failed to connect to Anthropic API" in str(exc_info.value)
