import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import datetime
from telegram.ext import ContextTypes
import anthropic

from bot.handlers.data_handlers import generate, workout
from services.garmin.models import GarminData, ExtractionConfig

@pytest.fixture
def mock_anthropic_response():
    """Create a mock Anthropic API response."""
    response = MagicMock()
    response.content = [MagicMock(text="Test AI response")]
    return response

@pytest.fixture
def mock_report_manager():
    """Create a mock SecureReportManager."""
    manager = MagicMock()
    manager.get_report.return_value = None
    manager.store_report.return_value = True
    return manager

@pytest.fixture
def mock_garmin_data():
    """Create mock Garmin data."""
    return GarminData()

@pytest.fixture
def mock_report_generator():
    """Create a mock ReportGenerator."""
    generator = MagicMock()
    generator.generate_activities_report.return_value = "Activities Report"
    generator.generate_metrics_report.return_value = "Metrics Report"
    return generator

@pytest.mark.asyncio
class TestGenerateCommand:
    """Tests for the /generate command."""

    async def test_generate_no_credentials(self, mock_update, mock_context, mock_secure_credential_manager):
        """Test generate command when no credentials are stored."""
        mock_secure_credential_manager.get_credentials.return_value = None
        
        with patch('bot.handlers.data_handlers.SecureCredentialManager',
                  return_value=mock_secure_credential_manager):
            
            await generate(mock_update, mock_context)
            
            mock_update.message.reply_text.assert_called_once()
            response = mock_update.message.reply_text.call_args[0][0]
            assert "No stored credentials" in response
            assert "/login" in response

    async def test_generate_fresh_data(
        self, mock_update, mock_context, mock_secure_credential_manager,
        mock_report_manager, mock_garmin_data, mock_report_generator,
        mock_anthropic_response
    ):
        """Test generate command with fresh data fetch."""
        # Setup mocks
        mock_secure_credential_manager.get_credentials.return_value = ("test@example.com", "password")
        mock_context.bot_data = {'anthropic_api_key': 'test-key'}
        
        with patch('bot.handlers.data_handlers.SecureCredentialManager',
                  return_value=mock_secure_credential_manager), \
             patch('bot.handlers.data_handlers.SecureReportManager',
                   return_value=mock_report_manager), \
             patch('bot.handlers.data_handlers.TriathlonCoachDataExtractor') as mock_extractor_class, \
             patch('bot.handlers.data_handlers.ReportGenerator',
                   return_value=mock_report_generator), \
             patch('bot.handlers.data_handlers.anthropic.Anthropic') as mock_anthropic_class:
            
            # Configure mocks
            mock_extractor = mock_extractor_class.return_value
            mock_extractor.extract_data.return_value = mock_garmin_data
            mock_anthropic = mock_anthropic_class.return_value
            mock_anthropic.messages.create.return_value = mock_anthropic_response
            
            await generate(mock_update, mock_context)
            
            # Verify data extraction
            mock_extractor.extract_data.assert_called_once()
            
            # Verify AI processing
            assert mock_anthropic.messages.create.call_count >= 1
            
            # Verify report storage
            mock_report_manager.store_report.assert_called_once()
            
            # Verify user messages
            assert mock_update.message.reply_text.call_count >= 3
            messages = [call[0][0] for call in mock_update.message.reply_text.call_args_list]
            assert any("Starting your training analysis" in msg for msg in messages)
            assert any("Data retrieved successfully" in msg for msg in messages)

    async def test_generate_cached_data(
        self, mock_update, mock_context, mock_secure_credential_manager,
        mock_report_manager
    ):
        """Test generate command with cached report."""
        # Setup cached report
        cached_report = ("Cached report content", datetime.datetime.now())
        mock_report_manager.get_report.return_value = cached_report
        mock_secure_credential_manager.get_credentials.return_value = ("test@example.com", "password")
        
        with patch('bot.handlers.data_handlers.SecureCredentialManager',
                  return_value=mock_secure_credential_manager), \
             patch('bot.handlers.data_handlers.SecureReportManager',
                   return_value=mock_report_manager):
            
            await generate(mock_update, mock_context)
            
            # Verify cached report usage
            assert mock_update.message.reply_text.call_count >= 1
            messages = [call[0][0] for call in mock_update.message.reply_text.call_args_list]
            assert any("Using your existing training report" in msg for msg in messages)

    async def test_generate_missing_api_key(
        self, mock_update, mock_context, mock_secure_credential_manager,
        mock_report_manager, mock_garmin_data
    ):
        """Test generate command when Anthropic API key is missing."""
        mock_secure_credential_manager.get_credentials.return_value = ("test@example.com", "password")
        mock_context.bot_data = {}  # No API key
        
        with patch('bot.handlers.data_handlers.SecureCredentialManager',
                  return_value=mock_secure_credential_manager), \
             patch('bot.handlers.data_handlers.SecureReportManager',
                   return_value=mock_report_manager):
            
            await generate(mock_update, mock_context)
            
            # Verify error message
            mock_update.message.reply_text.assert_called_with(
                "❌ Configuration error\\. Please contact support\\.",
                parse_mode="MARKDOWN_V2"
            )

@pytest.mark.asyncio
class TestWorkoutCommand:
    """Tests for the /workout command."""

    async def test_workout_no_report(self, mock_update, mock_context, mock_report_manager):
        """Test workout command when no report is available."""
        mock_report_manager.get_report.return_value = None
        
        with patch('bot.handlers.data_handlers.SecureReportManager',
                  return_value=mock_report_manager):
            
            await workout(mock_update, mock_context)
            
            mock_update.message.reply_text.assert_called_once()
            response = mock_update.message.reply_text.call_args[0][0]
            assert "No recent training report found" in response
            assert "/generate" in response

    async def test_workout_with_report(
        self, mock_update, mock_context, mock_report_manager,
        mock_anthropic_response
    ):
        """Test workout command with available report."""
        # Setup cached report
        cached_report = ("Cached report content", datetime.datetime.now())
        mock_report_manager.get_report.return_value = cached_report
        mock_context.bot_data = {'anthropic_api_key': 'test-key'}
        
        with patch('bot.handlers.data_handlers.SecureReportManager',
                  return_value=mock_report_manager), \
             patch('bot.handlers.data_handlers.anthropic.Anthropic') as mock_anthropic_class:
            
            mock_anthropic = mock_anthropic_class.return_value
            mock_anthropic.messages.create.return_value = mock_anthropic_response
            
            await workout(mock_update, mock_context)
            
            # Verify AI processing
            mock_anthropic.messages.create.assert_called_once()
            
            # Verify response messages
            assert mock_update.message.reply_text.call_count >= 2
            messages = [call[0][0] for call in mock_update.message.reply_text.call_args_list]
            assert any("Using your existing training report" in msg for msg in messages)

    async def test_workout_missing_api_key(self, mock_update, mock_context, mock_report_manager):
        """Test workout command when Anthropic API key is missing."""
        cached_report = ("Cached report content", datetime.datetime.now())
        mock_report_manager.get_report.return_value = cached_report
        mock_context.bot_data = {}  # No API key
        
        with patch('bot.handlers.data_handlers.SecureReportManager',
                  return_value=mock_report_manager):
            
            await workout(mock_update, mock_context)
            
            # Verify error message
            assert any("Configuration error" in call[0][0] 
                      for call in mock_update.message.reply_text.call_args_list)

    async def test_error_handling(
        self, mock_update, mock_context, mock_secure_credential_manager,
        mock_report_manager
    ):
        """Test error handling in data handlers."""
        mock_secure_credential_manager.get_credentials.return_value = ("test@example.com", "password")
        mock_context.bot_data = {'anthropic_api_key': 'test-key'}
        
        with patch('bot.handlers.data_handlers.SecureCredentialManager',
                  return_value=mock_secure_credential_manager), \
             patch('bot.handlers.data_handlers.SecureReportManager',
                   return_value=mock_report_manager), \
             patch('bot.handlers.data_handlers.TriathlonCoachDataExtractor',
                   side_effect=Exception("Test error")):
            
            await generate(mock_update, mock_context)
            
            # Verify error message
            error_messages = [
                call[0][0] for call in mock_update.message.reply_text.call_args_list
                if "Connection issue" in call[0][0]
            ]
            assert len(error_messages) == 1
            assert "Test error" in error_messages[0]
