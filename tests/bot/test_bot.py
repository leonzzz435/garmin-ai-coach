import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler
)

from bot.bot import TelegramBot, create_bot
from bot.handlers.conversation_handlers import (
    EXPECTING_EMAIL,
    EXPECTING_PASSWORD
)

@pytest.fixture
def mock_config():
    """Create a mock configuration."""
    config = MagicMock()
    config.bot_token = "test_token"
    config.anthropic_api_key = "test_api_key"
    return config

@pytest.fixture
def mock_application():
    """Create a mock Application."""
    app = MagicMock()
    app.bot_data = {}
    app.add_handler = MagicMock()
    app.add_error_handler = MagicMock()
    app.run_polling = AsyncMock()
    return app

class TestTelegramBot:
    """Tests for the TelegramBot class."""

    def test_initialization(self, mock_config):
        """Test bot initialization."""
        with patch('bot.bot.get_config', return_value=mock_config):
            bot = TelegramBot()
            
            assert bot.config == mock_config
            assert bot.app is None

    def test_setup(self, mock_config, mock_application):
        """Test bot setup process."""
        with patch('bot.bot.get_config', return_value=mock_config), \
             patch('bot.bot.ApplicationBuilder') as mock_builder:
            
            # Configure mock builder
            builder_instance = MagicMock()
            builder_instance.token.return_value.build.return_value = mock_application
            mock_builder.return_value = builder_instance
            
            # Create and setup bot
            bot = TelegramBot()
            bot.setup()
            
            # Verify application building
            builder_instance.token.assert_called_once_with(mock_config.bot_token)
            
            # Verify API key storage
            assert mock_application.bot_data['anthropic_api_key'] == mock_config.anthropic_api_key
            
            # Verify handler registration
            assert mock_application.add_handler.call_count > 0
            assert mock_application.add_error_handler.call_count == 1

    def test_handler_registration(self, mock_config, mock_application):
        """Test that all handlers are properly registered."""
        with patch('bot.bot.get_config', return_value=mock_config), \
             patch('bot.bot.ApplicationBuilder') as mock_builder:
            
            builder_instance = MagicMock()
            builder_instance.token.return_value.build.return_value = mock_application
            mock_builder.return_value = builder_instance
            
            bot = TelegramBot()
            bot.setup()
            
            # Get all handler registration calls
            handler_calls = [call[0][0] for call in mock_application.add_handler.call_args_list]
            
            # Verify conversation handler is registered first
            assert isinstance(handler_calls[0], ConversationHandler)
            
            # Verify all command handlers are registered
            command_handlers = [h for h in handler_calls if isinstance(h, CommandHandler)]
            assert len(command_handlers) >= 6  # start, generate, roadmap, help, clear_credentials, workout
            
            # Verify command mapping
            commands = [h.command for h in command_handlers]
            assert 'start' in commands
            assert 'generate' in commands
            assert 'roadmap' in commands
            assert 'help' in commands
            assert 'clear_credentials' in commands
            assert 'workout' in commands

    def test_conversation_handler_setup(self, mock_config, mock_application):
        """Test that conversation handler is properly configured."""
        with patch('bot.bot.get_config', return_value=mock_config), \
             patch('bot.bot.ApplicationBuilder') as mock_builder:
            
            builder_instance = MagicMock()
            builder_instance.token.return_value.build.return_value = mock_application
            mock_builder.return_value = builder_instance
            
            bot = TelegramBot()
            bot.setup()
            
            # Get conversation handler
            conv_handler = mock_application.add_handler.call_args_list[0][0][0]
            assert isinstance(conv_handler, ConversationHandler)
            
            # Verify states
            assert EXPECTING_EMAIL in conv_handler.states
            assert EXPECTING_PASSWORD in conv_handler.states
            
            # Verify handlers in states
            assert all(isinstance(h, MessageHandler) 
                      for h in conv_handler.states[EXPECTING_EMAIL])
            assert all(isinstance(h, MessageHandler) 
                      for h in conv_handler.states[EXPECTING_PASSWORD])

    def test_run_without_setup(self, mock_config):
        """Test that running without setup raises an error."""
        with patch('bot.bot.get_config', return_value=mock_config):
            bot = TelegramBot()
            
            with pytest.raises(RuntimeError) as exc_info:
                bot.run()
            assert "Bot not set up" in str(exc_info.value)

    def test_run_with_setup(self, mock_config, mock_application):
        """Test running the bot after setup."""
        with patch('bot.bot.get_config', return_value=mock_config), \
             patch('bot.bot.ApplicationBuilder') as mock_builder:
            
            builder_instance = MagicMock()
            builder_instance.token.return_value.build.return_value = mock_application
            mock_builder.return_value = builder_instance
            
            bot = TelegramBot()
            bot.setup()
            bot.run()
            
            mock_application.run_polling.assert_called_once()

    def test_create_bot_function(self, mock_config, mock_application):
        """Test the create_bot helper function."""
        with patch('bot.bot.get_config', return_value=mock_config), \
             patch('bot.bot.ApplicationBuilder') as mock_builder:
            
            builder_instance = MagicMock()
            builder_instance.token.return_value.build.return_value = mock_application
            mock_builder.return_value = builder_instance
            
            bot = create_bot()
            
            assert isinstance(bot, TelegramBot)
            assert bot.app is not None
            assert bot.config == mock_config

    def test_error_handler_registration(self, mock_config, mock_application):
        """Test that error handler is properly registered."""
        with patch('bot.bot.get_config', return_value=mock_config), \
             patch('bot.bot.ApplicationBuilder') as mock_builder:
            
            builder_instance = MagicMock()
            builder_instance.token.return_value.build.return_value = mock_application
            mock_builder.return_value = builder_instance
            
            bot = TelegramBot()
            bot.setup()
            
            mock_application.add_error_handler.assert_called_once()

    def test_missing_token(self, mock_config, mock_application):
        """Test handling of missing bot token."""
        mock_config.bot_token = None
        
        with patch('bot.bot.get_config', return_value=mock_config), \
             patch('bot.bot.ApplicationBuilder') as mock_builder:
            
            builder_instance = MagicMock()
            builder_instance.token.side_effect = ValueError("Token is required")
            mock_builder.return_value = builder_instance
            
            bot = TelegramBot()
            with pytest.raises(ValueError) as exc_info:
                bot.setup()
            assert "Token is required" in str(exc_info.value)

    def test_missing_api_key(self, mock_config, mock_application):
        """Test handling of missing Anthropic API key."""
        mock_config.anthropic_api_key = None
        
        with patch('bot.bot.get_config', return_value=mock_config), \
             patch('bot.bot.ApplicationBuilder') as mock_builder:
            
            builder_instance = MagicMock()
            builder_instance.token.return_value.build.return_value = mock_application
            mock_builder.return_value = builder_instance
            
            bot = TelegramBot()
            bot.setup()
            
            # Bot should still set up, but bot_data should have None for API key
            assert mock_application.bot_data['anthropic_api_key'] is None
