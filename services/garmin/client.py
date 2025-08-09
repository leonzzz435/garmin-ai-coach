import logging
from typing import Optional
from garminconnect import Garmin

logger = logging.getLogger(__name__)

class GarminConnectClient:
    
    def __init__(self):
        self._client: Optional[Garmin] = None
        
    def connect(self, email: str, password: str) -> None:
        try:
            logger.info("Initializing Garmin Connect client")
            self._client = Garmin(email, password)
            self._client.login()
            logger.info("Successfully connected to Garmin Connect")
        except Exception as e:
            logger.error(f"Failed to connect to Garmin Connect: {str(e)}")
            raise
    
    @property
    def client(self) -> Optional[Garmin]:
        return self._client
    
    def disconnect(self) -> None:
        if self._client:
            # Note: garminconnect doesn't have an explicit logout/disconnect method
            # So we just clear our reference
            self._client = None
            logger.info("Disconnected from Garmin Connect")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
