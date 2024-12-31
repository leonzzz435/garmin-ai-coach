"""Secure storage implementation for managing user credentials."""

from typing import Optional, Tuple
from .base import SecureStorageBase, StorageError

class SecureCredentialManager(SecureStorageBase):
    """Manager for securely storing and retrieving user credentials."""
    
    def __init__(self, user_id: str):
        """
        Initialize the credential manager for a specific user.
        
        Args:
            user_id: Unique identifier for the user
        """
        super().__init__(user_id, 'credentials')

    def store_credentials(self, email: str, password: str) -> bool:
        """
        Securely store user credentials.
        
        Args:
            email: User's email
            password: User's password
            
        Returns:
            bool: True if successful, False otherwise
            
        Raises:
            StorageError: If storing credentials fails
        """
        try:
            data = {
                'email': email,
                'password': password,
                'user_id': self.user_id
            }
            self._write(data)
            return True
        except StorageError:
            raise
        except Exception as e:
            raise StorageError(f"Failed to store credentials: {str(e)}") from e

    def get_credentials(self) -> Optional[Tuple[str, str]]:
        """
        Retrieve stored credentials.
        
        Returns:
            Optional[Tuple[str, str]]: (email, password) tuple if found, None otherwise
            
        Raises:
            StorageError: If retrieving credentials fails
        """
        try:
            data = self._read()
            if not data:
                return None
            
            if data['user_id'] != self.user_id:
                return None
                
            return data['email'], data['password']
        except StorageError:
            raise
        except Exception as e:
            raise StorageError(f"Failed to retrieve credentials: {str(e)}") from e

    def has_stored_credentials(self) -> bool:
        """
        Check if user has stored credentials.
        
        Returns:
            bool: True if credentials exist, False otherwise
        """
        return self.user_file.exists()
