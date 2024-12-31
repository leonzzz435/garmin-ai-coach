import pytest
from unittest.mock import patch, MagicMock
from telegram.constants import ParseMode

from bot.handlers.command_handlers import (
    start,
    help,
    roadmap,
    clear_credentials
)

@pytest.mark.asyncio
class TestCommandHandlers:
    """Tests for bot command handlers."""

    async def test_start_command(self, mock_update, mock_context):
        """Test the /start command response."""
        await start(mock_update, mock_context)
        
        mock_update.message.reply_text.assert_called_once()
        response = mock_update.message.reply_text.call_args[0][0]
        
        # Check for required elements in response
        assert mock_update.effective_user.first_name in response
        assert "Welcome to your AI Training Assistant" in response
        assert "/login" in response
        assert "/generate" in response
        assert "/workout" in response
        assert "/help" in response
        assert "Security Note" in response
        
        # Verify markdown formatting
        assert mock_update.message.reply_text.call_args[1]['parse_mode'] == ParseMode.MARKDOWN_V2

    async def test_help_command(self, mock_update, mock_context):
        """Test the /help command response."""
        await help(mock_update, mock_context)
        
        mock_update.message.reply_text.assert_called_once()
        response = mock_update.message.reply_text.call_args[0][0]
        
        # Check for all command sections
        assert "Available Commands" in response
        assert "Authentication" in response
        assert "Features" in response
        assert "Security Note" in response
        
        # Check for all commands
        assert "/login" in response
        assert "/clear_credentials" in response
        assert "/generate" in response
        assert "/workout" in response
        assert "/roadmap" in response
        assert "/help" in response
        
        # Verify markdown formatting
        assert mock_update.message.reply_text.call_args[1]['parse_mode'] == ParseMode.MARKDOWN_V2

    async def test_roadmap_command(self, mock_update, mock_context):
        """Test the /roadmap command response."""
        await roadmap(mock_update, mock_context)
        
        mock_update.message.reply_text.assert_called_once()
        response = mock_update.message.reply_text.call_args[0][0]
        
        # Check for roadmap sections
        assert "Development Roadmap" in response
        assert "Coming Soon" in response
        assert "General Training Q&A" in response
        assert "Smart Workout Suggestions" in response
        
        # Verify markdown formatting
        assert mock_update.message.reply_text.call_args[1]['parse_mode'] == ParseMode.MARKDOWN_V2

    async def test_clear_credentials_success(self, mock_update, mock_context, mock_secure_credential_manager):
        """Test successful credential clearing."""
        mock_secure_credential_manager.clear.return_value = True
        
        with patch('bot.handlers.command_handlers.SecureCredentialManager',
                  return_value=mock_secure_credential_manager):
            
            await clear_credentials(mock_update, mock_context)
            
            # Verify credential manager was called
            mock_secure_credential_manager.clear.assert_called_once()
            
            # Verify success message
            mock_update.message.reply_text.assert_called_once()
            response = mock_update.message.reply_text.call_args[0][0]
            assert "credentials have been cleared" in response
            assert "/login" in response
            assert mock_update.message.reply_text.call_args[1]['parse_mode'] == ParseMode.MARKDOWN_V2

    async def test_clear_credentials_failure(self, mock_update, mock_context, mock_secure_credential_manager):
        """Test credential clearing failure."""
        mock_secure_credential_manager.clear.return_value = False
        
        with patch('bot.handlers.command_handlers.SecureCredentialManager',
                  return_value=mock_secure_credential_manager):
            
            await clear_credentials(mock_update, mock_context)
            
            # Verify credential manager was called
            mock_secure_credential_manager.clear.assert_called_once()
            
            # Verify error message
            mock_update.message.reply_text.assert_called_once()
            response = mock_update.message.reply_text.call_args[0][0]
            assert "Failed to clear credentials" in response
            assert mock_update.message.reply_text.call_args[1]['parse_mode'] == ParseMode.MARKDOWN_V2

    async def test_markdown_escaping(self, mock_update, mock_context):
        """Test that markdown characters are properly escaped in responses."""
        # Set user name with markdown characters
        mock_update.effective_user.first_name = "User_with*markdown[chars]"
        
        await start(mock_update, mock_context)
        
        response = mock_update.message.reply_text.call_args[0][0]
        # Check that markdown characters are escaped
        assert "_with" not in response  # Should be escaped as \_with
        assert "*markdown" not in response  # Should be escaped as \*markdown
        assert "[chars]" not in response  # Should be escaped as \[chars\]

    @pytest.mark.parametrize("command_handler,expected_sections", [
        (start, ["Getting Started", "Main Features", "Security Note"]),
        (help, ["Authentication", "Features", "Security Note"]),
        (roadmap, ["Development Roadmap", "Coming Soon", "General Training Q&A"]),
    ])
    async def test_command_response_structure(self, mock_update, mock_context, command_handler, expected_sections):
        """Test that command responses have the expected structure."""
        await command_handler(mock_update, mock_context)
        
        response = mock_update.message.reply_text.call_args[0][0]
        for section in expected_sections:
            assert section in response

    async def test_clear_credentials_error_handling(self, mock_update, mock_context):
        """Test error handling during credential clearing."""
        with patch('bot.handlers.command_handlers.SecureCredentialManager',
                  side_effect=Exception("Storage error")):
            
            await clear_credentials(mock_update, mock_context)
            
            # Verify error message
            mock_update.message.reply_text.assert_called_once()
            response = mock_update.message.reply_text.call_args[0][0]
            assert "Failed to clear credentials" in response

    @pytest.mark.parametrize("command_handler", [start, help, roadmap])
    async def test_command_response_formatting(self, mock_update, mock_context, command_handler):
        """Test that command responses are properly formatted."""
        await command_handler(mock_update, mock_context)
        
        response = mock_update.message.reply_text.call_args[0][0]
        
        # Check for proper markdown escaping
        assert "\\" in response  # Should contain escape characters
        assert "```" not in response  # Should not contain raw markdown
        assert not response.startswith("*")  # Should not start with unescaped asterisk
        
        # Check for emoji usage
        assert "🏃‍♂️" in response or "📊" in response or "🔐" in response
