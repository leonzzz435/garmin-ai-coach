import pytest
from unittest.mock import MagicMock, AsyncMock
from telegram import Update, User, Message, Chat
from telegram.ext import ContextTypes

@pytest.fixture
def mock_user():
    """Create a mock Telegram user."""
    user = MagicMock(spec=User)
    user.id = 123456789
    user.first_name = "Test"
    user.last_name = "User"
    user.username = "testuser"
    return user

@pytest.fixture
def mock_chat():
    """Create a mock Telegram chat."""
    chat = MagicMock(spec=Chat)
    chat.id = 123456789
    chat.type = "private"
    return chat

@pytest.fixture
def mock_message():
    """Create a mock Telegram message."""
    message = AsyncMock(spec=Message)
    message.message_id = 1
    message.text = "Test message"
    message.chat = None  # Will be set by mock_update
    message.from_user = None  # Will be set by mock_update
    message.reply_text = AsyncMock()
    message.delete = AsyncMock()
    return message

@pytest.fixture
def mock_update(mock_user, mock_chat, mock_message):
    """Create a mock Telegram update."""
    update = MagicMock(spec=Update)
    update.effective_user = mock_user
    update.effective_chat = mock_chat
    
    # Set up message
    mock_message.chat = mock_chat
    mock_message.from_user = mock_user
    update.message = mock_message
    
    update.effective_message = mock_message
    return update

@pytest.fixture
def mock_context():
    """Create a mock Telegram context."""
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.bot = AsyncMock()
    context.bot.send_message = AsyncMock()
    return context

@pytest.fixture
def mock_secure_credential_manager():
    """Create a mock SecureCredentialManager."""
    manager = MagicMock()
    manager.has_stored_credentials = MagicMock(return_value=False)
    manager.store_credentials = MagicMock(return_value=True)
    return manager

@pytest.fixture
def mock_garmin_extractor():
    """Create a mock TriathlonCoachDataExtractor."""
    extractor = MagicMock()
    return extractor
