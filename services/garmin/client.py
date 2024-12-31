import logging
from typing import Optional
from garminconnect import Garmin

logger = logging.getLogger(__name__)

class GarminConnectClient:
    """Handles Garmin Connect API client setup and connection management"""
    
    def __init__(self):
        self._client: Optional[Garmin] = None
        
    def connect(self, email: str, password: str) -> None:
        """Initialize and connect to Garmin Connect.
        
        Args:
            email: Garmin Connect account email
            password: Garmin Connect account password
            
        Raises:
            Exception: If connection fails
        """
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
        """Get the underlying Garmin Connect client.
        
        Returns:
            The Garmin Connect client instance if connected, None otherwise
        """
        return self._client
    
    def is_connected(self) -> bool:
        """Check if client is connected to Garmin Connect.
        
        Returns:
            True if connected, False otherwise
        """
        return self._client is not None
    
    def disconnect(self) -> None:
        """Disconnect from Garmin Connect."""
        if self._client:
            # Note: garminconnect doesn't have an explicit logout/disconnect method
            # So we just clear our reference
            self._client = None
            logger.info("Disconnected from Garmin Connect")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
