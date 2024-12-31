import pytest
from unittest.mock import MagicMock

@pytest.fixture
def mock_telegram_update():
    update = MagicMock()
    update.message = MagicMock()
    update.message.text = "test message"
    update.message.chat = MagicMock()
    update.message.chat.id = 123456789
    update.message.from_user = MagicMock()
    update.message.from_user.id = 987654321
    return update

@pytest.fixture
def mock_garmin_client():
    client = MagicMock()
    client.get_activities = MagicMock(return_value=[])
    client.get_stats = MagicMock(return_value={})
    return client

@pytest.fixture
def mock_ai_client():
    client = MagicMock()
    client.generate_response = MagicMock(return_value="AI response")
    return client

@pytest.fixture
def mock_logger():
    logger = MagicMock()
    logger.info = MagicMock()
    logger.error = MagicMock()
    logger.debug = MagicMock()
    logger.warning = MagicMock()
    return logger
