"""
Storage module providing secure storage implementations for different data types.
"""

import datetime
from typing import Optional, Tuple, Protocol
from ..security import SecureStorageBase, StorageError

class CredentialStorage(SecureStorageBase):
    """Secure storage implementation for user credentials."""
    
    def __init__(self, user_id: str):
        """Initialize credential storage for a specific user."""
        super().__init__(user_id, 'credentials')
    
    def store(self, email: str, password: str) -> bool:
        """
        Store user credentials securely.
        
        Args:
            email: User's email address
            password: User's password
            
        Returns:
            bool: True if storage successful, False otherwise
            
        Raises:
            StorageError: If storage operation fails
        """
        data = {
            'email': email,
            'password': password,
            'user_id': self.user_id
        }
        try:
            self._write(data)
            return True
        except StorageError:
            return False
    
    def retrieve(self) -> Optional[Tuple[str, str]]:
        """
        Retrieve stored credentials.
        
        Returns:
            Optional[Tuple[str, str]]: Tuple of (email, password) if found, None otherwise
            
        Raises:
            StorageError: If retrieval operation fails
        """
        try:
            data = self._read()
            if not data or data.get('user_id') != self.user_id:
                return None
            return data['email'], data['password']
        except StorageError:
            return None
    
    def has_credentials(self) -> bool:
        """Check if user has stored credentials."""
        return self.user_file.exists()

class ReportStorage(SecureStorageBase):
    """Secure storage implementation for user reports."""
    
    def __init__(self, user_id: str):
        """Initialize report storage for a specific user."""
        super().__init__(user_id, 'reports')
    
    def store(self, report: str) -> bool:
        """
        Store user's report with timestamp.
        
        Args:
            report: Report content to store
            
        Returns:
            bool: True if storage successful, False otherwise
            
        Raises:
            StorageError: If storage operation fails
        """
        data = {
            'report': report,
            'timestamp': datetime.datetime.now().isoformat(),
            'user_id': self.user_id
        }
        try:
            self._write(data)
            return True
        except StorageError:
            return False
    
    def retrieve(self, max_age_hours: int = 12) -> Optional[Tuple[str, datetime.datetime]]:
        """
        Retrieve stored report if not expired.
        
        Args:
            max_age_hours: Maximum age of report in hours before considered expired
            
        Returns:
            Optional[Tuple[str, datetime.datetime]]: Tuple of (report, timestamp) if found and not expired,
                                                   None otherwise
            
        Raises:
            StorageError: If retrieval operation fails
        """
        try:
            data = self._read()
            if not data or data.get('user_id') != self.user_id:
                return None
            
            timestamp = datetime.datetime.fromisoformat(data['timestamp'])
            current_time = datetime.datetime.now()
            
            # Check if report is expired
            if (current_time - timestamp).total_seconds() > (max_age_hours * 3600):
                return None
                
            return data['report'], timestamp
        except StorageError:
            return None

__all__ = ['CredentialStorage', 'ReportStorage']
