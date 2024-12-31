import pytest
from unittest.mock import patch, MagicMock
from telegram.ext import ConversationHandler

from bot.handlers.conversation_handlers import (
    start_login,
    process_email,
    process_password,
    cancel,
    EXPECTING_EMAIL,
    EXPECTING_PASSWORD,
    user_data
)

@pytest.mark.asyncio
class TestLoginConversation:
    """Tests for the login conversation flow."""

    async def test_start_login_new_user(self, mock_update, mock_context, mock_secure_credential_manager):
        """Test starting login for a new user."""
        with patch('bot.handlers.conversation_handlers.SecureCredentialManager', 
                  return_value=mock_secure_credential_manager):
            
            result = await start_login(mock_update, mock_context)
            
            # Verify the response
            mock_update.message.reply_text.assert_called_once()
            assert "Please enter your Garmin email address" in mock_update.message.reply_text.call_args[0][0]
            assert result == EXPECTING_EMAIL
            assert mock_update.effective_user.id in user_data

    async def test_start_login_existing_credentials(self, mock_update, mock_context, mock_secure_credential_manager):
        """Test starting login when user already has credentials."""
        mock_secure_credential_manager.has_stored_credentials.return_value = True
        
        with patch('bot.handlers.conversation_handlers.SecureCredentialManager',
                  return_value=mock_secure_credential_manager):
            
            result = await start_login(mock_update, mock_context)
            
            # Verify the response
            mock_update.message.reply_text.assert_called_once()
            assert "You already have stored credentials" in mock_update.message.reply_text.call_args[0][0]
            assert result == ConversationHandler.END

    async def test_process_email(self, mock_update, mock_context):
        """Test processing email input."""
        test_email = "test@example.com"
        mock_update.message.text = test_email
        user_id = mock_update.effective_user.id
        user_data[user_id] = {}
        
        result = await process_email(mock_update, mock_context)
        
        # Verify email storage and response
        assert user_data[user_id]["temp_email"] == test_email
        mock_update.message.reply_text.assert_called_once()
        assert "Now please enter your password" in mock_update.message.reply_text.call_args[0][0]
        assert result == EXPECTING_PASSWORD

    async def test_process_password_success(self, mock_update, mock_context, mock_secure_credential_manager, mock_garmin_extractor):
        """Test successful password processing and login."""
        test_email = "test@example.com"
        test_password = "password123"
        user_id = mock_update.effective_user.id
        user_data[user_id] = {"temp_email": test_email}
        mock_update.message.text = test_password
        
        with patch('bot.handlers.conversation_handlers.SecureCredentialManager',
                  return_value=mock_secure_credential_manager), \
             patch('bot.handlers.conversation_handlers.TriathlonCoachDataExtractor',
                   return_value=mock_garmin_extractor):
            
            result = await process_password(mock_update, mock_context)
            
            # Verify password message deletion
            mock_update.message.delete.assert_called_once()
            
            # Verify Garmin connection test
            mock_garmin_extractor.assert_called_once_with(test_email, test_password)
            
            # Verify credential storage
            mock_secure_credential_manager.store_credentials.assert_called_once_with(
                test_email, test_password
            )
            
            # Verify success message
            success_call = [call for call in mock_context.bot.send_message.call_args_list 
                          if "Connection successful" in call[1]['text']]
            assert len(success_call) == 1
            
            assert result == ConversationHandler.END

    async def test_process_password_garmin_error(self, mock_update, mock_context, mock_secure_credential_manager):
        """Test password processing with Garmin connection error."""
        test_email = "test@example.com"
        test_password = "wrong_password"
        user_id = mock_update.effective_user.id
        user_data[user_id] = {"temp_email": test_email}
        mock_update.message.text = test_password
        
        with patch('bot.handlers.conversation_handlers.SecureCredentialManager',
                  return_value=mock_secure_credential_manager), \
             patch('bot.handlers.conversation_handlers.TriathlonCoachDataExtractor',
                   side_effect=Exception("Connection failed")):
            
            result = await process_password(mock_update, mock_context)
            
            # Verify password message deletion
            mock_update.message.delete.assert_called_once()
            
            # Verify error message
            error_call = [call for call in mock_context.bot.send_message.call_args_list 
                         if "Connection failed" in call[1]['text']]
            assert len(error_call) == 1
            
            # Verify credentials were not stored
            mock_secure_credential_manager.store_credentials.assert_not_called()
            
            assert result == ConversationHandler.END

    async def test_process_password_storage_error(self, mock_update, mock_context, mock_secure_credential_manager, mock_garmin_extractor):
        """Test password processing with credential storage error."""
        test_email = "test@example.com"
        test_password = "password123"
        user_id = mock_update.effective_user.id
        user_data[user_id] = {"temp_email": test_email}
        mock_update.message.text = test_password
        mock_secure_credential_manager.store_credentials.return_value = False
        
        with patch('bot.handlers.conversation_handlers.SecureCredentialManager',
                  return_value=mock_secure_credential_manager), \
             patch('bot.handlers.conversation_handlers.TriathlonCoachDataExtractor',
                   return_value=mock_garmin_extractor):
            
            result = await process_password(mock_update, mock_context)
            
            # Verify storage failure message
            failure_call = [call for call in mock_context.bot.send_message.call_args_list 
                          if "failed to store credentials" in call[1]['text']]
            assert len(failure_call) == 1
            
            assert result == ConversationHandler.END

    async def test_cancel(self, mock_update, mock_context):
        """Test conversation cancellation."""
        result = await cancel(mock_update, mock_context)
        
        mock_update.message.reply_text.assert_called_once()
        assert "Login cancelled" in mock_update.message.reply_text.call_args[0][0]
        assert result == ConversationHandler.END

    @pytest.mark.parametrize("user_id,data", [
        (123, {"temp_email": "test@example.com"}),
        (456, {"temp_email": "another@example.com"}),
    ])
    async def test_user_data_isolation(self, mock_update, mock_context, user_id, data):
        """Test that user data is properly isolated between users."""
        mock_update.effective_user.id = user_id
        user_data[user_id] = data.copy()
        
        # Process email for this user
        mock_update.message.text = "new@example.com"
        await process_email(mock_update, mock_context)
        
        # Verify only this user's data was updated
        assert user_data[user_id]["temp_email"] == "new@example.com"
        for other_id, other_data in user_data.items():
            if other_id != user_id:
                assert other_data == data

    async def test_cleanup_after_completion(self, mock_update, mock_context, mock_secure_credential_manager, mock_garmin_extractor):
        """Test that temporary data is cleaned up after successful login."""
        user_id = mock_update.effective_user.id
        test_email = "test@example.com"
        test_password = "password123"
        user_data[user_id] = {"temp_email": test_email}
        mock_update.message.text = test_password
        
        with patch('bot.handlers.conversation_handlers.SecureCredentialManager',
                  return_value=mock_secure_credential_manager), \
             patch('bot.handlers.conversation_handlers.TriathlonCoachDataExtractor',
                   return_value=mock_garmin_extractor):
            
            await process_password(mock_update, mock_context)
            
            # Verify user data was cleaned up
            assert user_id not in user_data or "temp_email" not in user_data[user_id]
