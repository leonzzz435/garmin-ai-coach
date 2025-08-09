
import logging
from typing import Optional, Any, Dict
from .base import SecureStorageBase, StorageError

# Configure logging
logger = logging.getLogger(__name__)

class CacheError(StorageError):
    pass

class SecureMetricsCache(SecureStorageBase):
    
    def __init__(self, user_id: str):
        super().__init__(user_id, 'cache_metrics')
    
    def store(self, data: Dict[str, Any]) -> bool:
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
        try:
            data = self._read()
            if not data or data['user_id'] != self.user_id:
                return None
            return data['data']
        except Exception as e:
            raise CacheError(f"Failed to retrieve metrics: {str(e)}") from e

class SecureActivityCache(SecureStorageBase):
    
    def __init__(self, user_id: str):
        super().__init__(user_id, 'cache_activity')
    
    def store(self, data: Dict[str, Any]) -> bool:
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
        try:
            data = self._read()
            if not data or data['user_id'] != self.user_id:
                return None
            return data['data']
        except Exception as e:
            raise CacheError(f"Failed to retrieve activity data: {str(e)}") from e

class SecurePhysiologyCache(SecureStorageBase):
    
    def __init__(self, user_id: str):
        super().__init__(user_id, 'cache_physiology')
    
    def store(self, data: Dict[str, Any]) -> bool:
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
        try:
            data = self._read()
            if not data or data['user_id'] != self.user_id:
                return None
            return data['data']
        except Exception as e:
            raise CacheError(f"Failed to retrieve physiology data: {str(e)}") from e
