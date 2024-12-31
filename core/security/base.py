"""Base classes for secure storage functionality."""

import os
import json
from pathlib import Path
from typing import Any, Optional
from cryptography.fernet import Fernet, InvalidToken

class SecurityError(Exception):
    """Base exception for security-related errors."""
    pass

class StorageError(SecurityError):
    """Exception for storage-related errors."""
    pass

class SecureStorageBase:
    """Base class for secure storage implementations."""
    
    def __init__(self, user_id: str, storage_type: str):
        """
        Initialize secure storage for a specific user and type.
        
        Args:
            user_id: Unique identifier for the user
            storage_type: Type of storage (e.g., 'credentials', 'reports')
            
        Raises:
            StorageError: If storage setup fails
        """
        self.user_id = str(user_id)
        self.storage_type = storage_type
        self._setup_storage()
    
    def _setup_storage(self) -> None:
        """
        Set up the secure storage directory structure.
        
        Raises:
            StorageError: If directory creation or permissions setup fails
        """
        try:
            # Create secure storage directory in user's home
            storage_dir = Path.home() / '.garmin_bot' / self.storage_type
            storage_dir.mkdir(parents=True, exist_ok=True)
            
            # Ensure directory permissions are restricted
            os.chmod(storage_dir.parent, 0o700)
            os.chmod(storage_dir, 0o700)
            
            self.user_file = storage_dir / f'{self.user_id}.enc'
            
            # Generate or load encryption key
            key_file = storage_dir / '.key'
            if not key_file.exists():
                key = Fernet.generate_key()
                key_file.write_bytes(key)
                os.chmod(key_file, 0o600)
            else:
                key = key_file.read_bytes()
                
            self.cipher_suite = Fernet(key)
            
        except Exception as e:
            raise StorageError(f"Failed to setup secure storage: {str(e)}") from e
    
    def _encrypt(self, data: Any) -> bytes:
        """
        Encrypt data using Fernet encryption.
        
        Args:
            data: Data to encrypt (must be JSON serializable)
            
        Returns:
            bytes: Encrypted data
            
        Raises:
            StorageError: If encryption fails
        """
        try:
            json_data = json.dumps(data)
            return self.cipher_suite.encrypt(json_data.encode())
        except Exception as e:
            raise StorageError(f"Failed to encrypt data: {str(e)}") from e
    
    def _decrypt(self, encrypted_data: bytes) -> Any:
        """
        Decrypt data using Fernet encryption.
        
        Args:
            encrypted_data: Data to decrypt
            
        Returns:
            Any: Decrypted data
            
        Raises:
            StorageError: If decryption fails
        """
        try:
            decrypted_data = self.cipher_suite.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode())
        except InvalidToken as e:
            raise StorageError("Invalid encryption token or corrupted data") from e
        except Exception as e:
            raise StorageError(f"Failed to decrypt data: {str(e)}") from e
    
    def _write(self, data: Any) -> None:
        """
        Write encrypted data to storage.
        
        Args:
            data: Data to store (must be JSON serializable)
            
        Raises:
            StorageError: If write operation fails
        """
        try:
            encrypted_data = self._encrypt(data)
            self.user_file.write_bytes(encrypted_data)
            os.chmod(self.user_file, 0o600)
        except Exception as e:
            raise StorageError(f"Failed to write data: {str(e)}") from e
    
    def _read(self) -> Optional[Any]:
        """
        Read and decrypt data from storage.
        
        Returns:
            Optional[Any]: Decrypted data if file exists, None otherwise
            
        Raises:
            StorageError: If read operation fails
        """
        try:
            if not self.user_file.exists():
                return None
            encrypted_data = self.user_file.read_bytes()
            return self._decrypt(encrypted_data)
        except Exception as e:
            raise StorageError(f"Failed to read data: {str(e)}") from e
    
    def clear(self) -> bool:
        """
        Remove stored data.
        
        Returns:
            bool: True if successful or file didn't exist, False otherwise
        """
        try:
            if self.user_file.exists():
                self.user_file.unlink()
            return True
        except Exception as e:
            raise StorageError(f"Failed to clear data: {str(e)}") from e
