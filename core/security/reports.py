"""Secure storage implementation for managing user reports."""

import datetime
from typing import Optional, Tuple
from .base import SecureStorageBase, StorageError

class SecureReportManager(SecureStorageBase):
    """Manager for securely storing and retrieving user reports with timestamp validation."""
    
    def __init__(self, user_id: str):
        """
        Initialize the report manager for a specific user.
        
        Args:
            user_id: Unique identifier for the user
        """
        super().__init__(user_id, 'reports')

    def store_report(self, report: str) -> bool:
        """
        Securely store user's latest report with timestamp.
        
        Args:
            report: Report content to store
            
        Returns:
            bool: True if successful, False otherwise
            
        Raises:
            StorageError: If storing report fails
        """
        try:
            data = {
                'report': report,
                'timestamp': datetime.datetime.now().isoformat(),
                'user_id': self.user_id
            }
            self._write(data)
            return True
        except StorageError:
            raise
        except Exception as e:
            raise StorageError(f"Failed to store report: {str(e)}") from e

    def get_report(self) -> Optional[Tuple[str, datetime.datetime]]:
        """
        Retrieve stored report and its timestamp if not expired.
        
        Returns:
            Optional[Tuple[str, datetime.datetime]]: (report, timestamp) tuple if found and not expired,
            None otherwise
            
        Raises:
            StorageError: If retrieving report fails
        """
        try:
            data = self._read()
            if not data:
                return None
            
            if data['user_id'] != self.user_id:
                return None

            timestamp = datetime.datetime.fromisoformat(data['timestamp'])
            current_time = datetime.datetime.now()
            
            # Check if report is less than 12 hours old
            if (current_time - timestamp).total_seconds() < 43200:  # 12 hours
                return data['report'], timestamp
            
            return None
        except StorageError:
            raise
        except Exception as e:
            raise StorageError(f"Failed to retrieve report: {str(e)}") from e
