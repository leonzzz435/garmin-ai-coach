import pytest
from unittest.mock import Mock, patch, mock_open
import tempfile
import os
from pathlib import Path
from core.security.base import SecureStorageBase, StorageError
from core.security.credentials import SecureCredentialManager


class TestSecureStorageBaseCharacterization:
    
    @patch('core.security.base.Path')
    @patch('core.security.base.Fernet')
    def test_setup_storage_creates_directory_structure(self, mock_fernet, mock_path):
        mock_home = Mock()
        mock_garmin_dir = Mock()
        mock_storage_dir = Mock()
        mock_user_file = Mock()
        mock_key_file = Mock()

        mock_path.home.return_value = mock_home
        mock_home.__truediv__ = Mock(return_value=mock_garmin_dir)
        mock_garmin_dir.__truediv__ = Mock(return_value=mock_storage_dir)
        mock_storage_dir.exists.return_value = False
        mock_storage_dir.__truediv__ = Mock(side_effect=[mock_user_file, mock_key_file])
        mock_key_file.exists.return_value = False

        with patch('core.security.base.os.stat'), patch('core.security.base.os.chmod'):
            base = SecureStorageBase("123", "test_type")
        
        mock_storage_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)
    
    @patch('core.security.base.Path')
    @patch('core.security.base.Fernet')
    @patch('core.security.base.os.chmod')
    def test_setup_storage_sets_correct_permissions(self, mock_chmod, mock_fernet, mock_path):
        mock_home = Mock()
        mock_garmin_dir = Mock()
        mock_storage_dir = Mock()
        mock_user_file = Mock()
        mock_key_file = Mock()
        
        mock_path.home.return_value = mock_home
        mock_home.__truediv__ = Mock(return_value=mock_garmin_dir)
        mock_garmin_dir.__truediv__ = Mock(return_value=mock_storage_dir)
        mock_storage_dir.exists.return_value = True
        mock_storage_dir.__truediv__ = Mock(side_effect=[mock_user_file, mock_key_file])
        mock_key_file.exists.return_value = True
        
        with patch('core.security.base.os.stat') as mock_stat:
            mock_stat.return_value.st_mode = 0o755  # Wrong permissions
            base = SecureStorageBase("123", "test_type")
            
        mock_chmod.assert_called()  # Should fix permissions
    
    @patch('core.security.base.Path')
    @patch('core.security.base.Fernet')
    def test_encrypt_decrypt_round_trip(self, mock_fernet_class, mock_path):
        mock_cipher = Mock()
        mock_fernet_class.return_value = mock_cipher
        mock_cipher.encrypt.return_value = b'encrypted_data'
        mock_cipher.decrypt.return_value = b'{"test": "data"}'

        mock_home = Mock()
        mock_garmin_dir = Mock()
        mock_storage_dir = Mock()
        mock_user_file = Mock()
        mock_key_file = Mock()

        mock_path.home.return_value = mock_home
        mock_home.__truediv__ = Mock(return_value=mock_garmin_dir)
        mock_garmin_dir.__truediv__ = Mock(return_value=mock_storage_dir)
        mock_storage_dir.exists.return_value = True
        mock_storage_dir.__truediv__ = Mock(side_effect=[mock_user_file, mock_key_file])
        mock_key_file.exists.return_value = True

        with patch('core.security.base.os.stat'), patch('core.security.base.os.chmod'):
            base = SecureStorageBase("123", "test_type")
            base.cipher_suite = mock_cipher
            
            data = {"test": "data"}
            encrypted = base._encrypt(data)
            decrypted = base._decrypt(encrypted)
            
            assert decrypted == data
    
    @patch('core.security.base.Path')
    @patch('core.security.base.Fernet')
    def test_write_includes_verification(self, mock_fernet_class, mock_path):
        mock_cipher = Mock()
        mock_fernet_class.return_value = mock_cipher
        mock_cipher.encrypt.return_value = b'encrypted_data'
        mock_cipher.decrypt.return_value = b'{"test": "data"}'
        
        mock_home = Mock()
        mock_garmin_dir = Mock()
        mock_storage_dir = Mock()
        
        mock_path.home.return_value = mock_home
        mock_home.__truediv__ = Mock(return_value=mock_garmin_dir)
        mock_garmin_dir.__truediv__ = Mock(return_value=mock_storage_dir)
        mock_storage_dir.exists.return_value = True
        
        mock_file = Mock()
        mock_storage_dir.__truediv__ = Mock(return_value=mock_file)
        mock_file.parent = mock_storage_dir
        mock_file.write_bytes = Mock()
        
        with patch('core.security.base.os.stat'), patch('core.security.base.os.chmod'), \
             patch('core.security.base.os.fsync'), patch('builtins.open', mock_open()):
            base = SecureStorageBase("123", "test_type")
            base.cipher_suite = mock_cipher
            base.user_file = mock_file
            
            # Mock _read to return the same data for verification
            base._read = Mock(return_value={"test": "data"})
            
            base._write({"test": "data"})
            
            mock_file.write_bytes.assert_called_once_with(b'encrypted_data')
            base._read.assert_called_once()  # Verification read


class TestSecureCredentialManagerCharacterization:
    
    @patch('core.security.credentials.SecureStorageBase.__init__')
    def test_initialization_calls_parent_with_credentials_type(self, mock_parent_init):
        mock_parent_init.return_value = None
        
        manager = SecureCredentialManager("123")
        
        mock_parent_init.assert_called_once_with("123", 'credentials')
    
    @patch('core.security.credentials.SecureStorageBase._write')
    def test_store_credentials_includes_user_id_validation(self, mock_write):
        manager = SecureCredentialManager("123")
        manager.user_id = "123"
        
        result = manager.store_credentials("test@example.com", "password")
        
        mock_write.assert_called_once_with({
            'email': 'test@example.com', 
            'password': 'password', 
            'user_id': '123'
        })
        assert result is True
    
    @patch('core.security.credentials.SecureStorageBase._read')
    def test_get_credentials_validates_user_id_match(self, mock_read):
        mock_read.return_value = {
            'email': 'test@example.com',
            'password': 'password',
            'user_id': '456'  # Different user ID
        }
        
        manager = SecureCredentialManager("123")
        manager.user_id = "123"
        
        result = manager.get_credentials()
        
        assert result is None  # Should return None for mismatched user_id
    
    @patch('core.security.credentials.SecureStorageBase._read')
    def test_get_credentials_returns_tuple_on_success(self, mock_read):
        mock_read.return_value = {
            'email': 'test@example.com',
            'password': 'password',
            'user_id': '123'
        }
        
        manager = SecureCredentialManager("123")
        manager.user_id = "123"
        
        result = manager.get_credentials()
        
        assert result == ('test@example.com', 'password')
        assert isinstance(result, tuple)
    
    @patch('core.security.credentials.SecureStorageBase._read')
    def test_get_credentials_handles_no_data(self, mock_read):
        mock_read.return_value = None
        
        manager = SecureCredentialManager("123")
        
        result = manager.get_credentials()
        
        assert result is None
    
    def test_has_stored_credentials_checks_file_existence(self):
        manager = SecureCredentialManager("123")
        mock_file = Mock()
        mock_file.exists.return_value = True
        manager.user_file = mock_file
        
        result = manager.has_stored_credentials()
        
        assert result is True
        mock_file.exists.assert_called_once()


class TestSecurityErrorHandlingCharacterization:
    
    @patch('core.security.base.Path')
    @patch('core.security.base.Fernet')
    def test_storage_error_propagation_on_setup_failure(self, mock_fernet, mock_path):
        mock_path.home.side_effect = Exception("Filesystem error")
        
        with pytest.raises(StorageError) as exc_info:
            SecureStorageBase("123", "test_type")
        
        assert "Failed to setup secure storage" in str(exc_info.value)
    
    @patch('core.security.base.Path')
    @patch('core.security.base.Fernet')
    def test_encryption_error_handling(self, mock_fernet_class, mock_path):
        mock_cipher = Mock()
        mock_fernet_class.return_value = mock_cipher
        mock_cipher.encrypt.side_effect = Exception("Encryption failed")

        mock_home = Mock()
        mock_garmin_dir = Mock()
        mock_storage_dir = Mock()
        mock_user_file = Mock()
        mock_key_file = Mock()

        mock_path.home.return_value = mock_home
        mock_home.__truediv__ = Mock(return_value=mock_garmin_dir)
        mock_garmin_dir.__truediv__ = Mock(return_value=mock_storage_dir)
        mock_storage_dir.exists.return_value = True
        mock_storage_dir.__truediv__ = Mock(side_effect=[mock_user_file, mock_key_file])
        mock_key_file.exists.return_value = True

        with patch('core.security.base.os.stat'), patch('core.security.base.os.chmod'):
            base = SecureStorageBase("123", "test_type")
            base.cipher_suite = mock_cipher
            
            with pytest.raises(StorageError) as exc_info:
                base._encrypt({"test": "data"})
            
            assert "Failed to encrypt data" in str(exc_info.value)
    
    @patch('core.security.base.Path')
    @patch('core.security.base.Fernet')
    def test_file_sync_and_verification_behavior(self, mock_fernet_class, mock_path):
        mock_cipher = Mock()
        mock_fernet_class.return_value = mock_cipher
        mock_cipher.encrypt.return_value = b'encrypted_data'
        mock_cipher.decrypt.return_value = b'{"test": "data"}'
        
        mock_home = Mock()
        mock_garmin_dir = Mock()
        mock_storage_dir = Mock()
        
        mock_path.home.return_value = mock_home
        mock_home.__truediv__ = Mock(return_value=mock_garmin_dir)
        mock_garmin_dir.__truediv__ = Mock(return_value=mock_storage_dir)
        mock_storage_dir.exists.return_value = True
        
        mock_file = Mock()
        mock_storage_dir.__truediv__ = Mock(return_value=mock_file)
        mock_file.parent = mock_storage_dir
        mock_file.write_bytes = Mock()
        
        with patch('core.security.base.os.stat'), patch('core.security.base.os.chmod'), \
             patch('core.security.base.os.fsync') as mock_fsync, \
             patch('builtins.open', mock_open()) as mock_file_open:
            
            base = SecureStorageBase("123", "test_type")
            base.cipher_suite = mock_cipher
            base.user_file = mock_file
            
            # Mock _read to return the same data for verification
            base._read = Mock(return_value={"test": "data"})
            
            base._write({"test": "data"})
            
            # Verify fsync is called for data persistence
            mock_fsync.assert_called()
            # Verify verification read occurs
            base._read.assert_called()


class TestSecurityFileSystemBehavior:
    
    @patch('core.security.base.Path')
    @patch('core.security.base.Fernet')
    def test_clear_includes_directory_sync(self, mock_fernet_class, mock_path):
        mock_cipher = Mock()
        mock_fernet_class.return_value = mock_cipher
        
        mock_home = Mock()
        mock_garmin_dir = Mock()
        mock_storage_dir = Mock()
        
        mock_path.home.return_value = mock_home
        mock_home.__truediv__ = Mock(return_value=mock_garmin_dir)
        mock_garmin_dir.__truediv__ = Mock(return_value=mock_storage_dir)
        mock_storage_dir.exists.return_value = True
        
        mock_file = Mock()
        mock_storage_dir.__truediv__ = Mock(return_value=mock_file)
        mock_file.parent = mock_storage_dir
        mock_file.exists.return_value = True
        
        with patch('core.security.base.os.stat'), patch('core.security.base.os.chmod'), \
             patch('core.security.base.os.open') as mock_open, \
             patch('core.security.base.os.fsync') as mock_fsync, \
             patch('core.security.base.os.close') as mock_close:
            
            mock_open.return_value = 123  # File descriptor
            
            base = SecureStorageBase("123", "test_type")
            base.cipher_suite = mock_cipher
            base.user_file = mock_file
            base._read = Mock(side_effect=[{"old": "data"}, None])  # Before and after deletion
            
            # Mock successful deletion
            mock_file.unlink = Mock()
            def unlink_side_effect():
                mock_file.exists.return_value = False
            mock_file.unlink.side_effect = unlink_side_effect
            
            result = base.clear()
            
            # Verify directory sync for persistence
            mock_open.assert_called()
            mock_fsync.assert_called_with(123)
            mock_close.assert_called_with(123)
            assert result is True