"""Secure caching implementation for analysis data."""

import logging
from typing import Optional, Any, Dict
from .base import SecureStorageBase, StorageError

# Configure logging
logger = logging.getLogger(__name__)

class CacheError(StorageError):
    """Exception for cache-related errors."""

class SecureMetricsCache(SecureStorageBase):
    """Secure cache for metrics data."""
    
    def __init__(self, user_id: str):
        """Initialize metrics cache for a specific user."""
        super().__init__(user_id, 'cache_metrics')
    
    def store(self, data: Dict[str, Any]) -> bool:
        """
        Store metrics data.
        
        Args:
            data: Metrics data to cache
            
        Returns:
            bool: True if successful
            
        Raises:
            CacheError: If storing fails
        """
        try:
            cache_entry = {
                'data': data,
                'user_id': self.user_id
            }
            self._write(cache_entry)
            return True
        except Exception as e:
            raise CacheError(f"Failed to store metrics: {str(e)}") from e
    
    def get(self) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached metrics.
        
        Returns:
            Optional[Dict[str, Any]]: Cached data if exists
            
        Raises:
            CacheError: If retrieval fails
        """
        try:
            data = self._read()
            if not data or data['user_id'] != self.user_id:
                return None
            return data['data']
        except Exception as e:
            raise CacheError(f"Failed to retrieve metrics: {str(e)}") from e

class SecureActivityCache(SecureStorageBase):
    """Secure cache for activity data."""
    
    def __init__(self, user_id: str):
        """Initialize activity cache for a specific user."""
        super().__init__(user_id, 'cache_activity')
    
    def store(self, data: Dict[str, Any]) -> bool:
        """
        Store activity data.
        
        Args:
            data: Activity data to cache
            
        Returns:
            bool: True if successful
            
        Raises:
            CacheError: If storing fails
        """
        try:
            cache_entry = {
                'data': data,
                'user_id': self.user_id
            }
            self._write(cache_entry)
            return True
        except Exception as e:
            raise CacheError(f"Failed to store activity data: {str(e)}") from e
    
    def get(self) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached activity data.
        
        Returns:
            Optional[Dict[str, Any]]: Cached data if exists
            
        Raises:
            CacheError: If retrieval fails
        """
        try:
            data = self._read()
            if not data or data['user_id'] != self.user_id:
                return None
            return data['data']
        except Exception as e:
            raise CacheError(f"Failed to retrieve activity data: {str(e)}") from e

class SecurePhysiologyCache(SecureStorageBase):
    """Secure cache for physiology data."""
    
    def __init__(self, user_id: str):
        """Initialize physiology cache for a specific user."""
        super().__init__(user_id, 'cache_physiology')
    
    def store(self, data: Dict[str, Any]) -> bool:
        """
        Store physiology data.
        
        Args:
            data: Physiology data to cache
            
        Returns:
            bool: True if successful
            
        Raises:
            CacheError: If storing fails
        """
        try:
            cache_entry = {
                'data': data,
                'user_id': self.user_id
            }
            self._write(cache_entry)
            return True
        except Exception as e:
            raise CacheError(f"Failed to store physiology data: {str(e)}") from e
    
    def get(self) -> Optional[Dict[str, Any]]:
        """
        Retrieve cached physiology data.
        
        Returns:
            Optional[Dict[str, Any]]: Cached data if exists
            
        Raises:
            CacheError: If retrieval fails
        """
        try:
            data = self._read()
            if not data or data['user_id'] != self.user_id:
                return None
            return data['data']
        except Exception as e:
            raise CacheError(f"Failed to retrieve physiology data: {str(e)}") from e
