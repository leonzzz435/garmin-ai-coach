"""User tracking functionality for the Telegram bot."""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

# Configure logging
logger = logging.getLogger(__name__)

class UserTracker:
    """Track users who interact with the bot."""
    
    def __init__(self):
        """Initialize the user tracker."""
        self.storage_dir = Path.home() / '.garmin_bot' / 'users'
        self.users_file = self.storage_dir / 'users.json'
        self._setup_storage()
    
    def _setup_storage(self) -> None:
        """Set up the storage directory and files."""
        try:
            # Create directory if it doesn't exist
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            
            # Create users file if it doesn't exist
            if not self.users_file.exists():
                self._save_users({})
                
        except Exception as e:
            logger.error(f"Failed to setup user storage: {e}")
            raise
    
    def _load_users(self) -> Dict:
        """Load users from storage."""
        try:
            if self.users_file.exists():
                return json.loads(self.users_file.read_text())
            return {}
        except Exception as e:
            logger.error(f"Failed to load users: {e}")
            return {}
    
    def _save_users(self, users: Dict) -> None:
        """Save users to storage."""
        try:
            self.users_file.write_text(json.dumps(users, indent=2))
        except Exception as e:
            logger.error(f"Failed to save users: {e}")
            raise
    
    def track_user(self, user_id: int, first_name: str, username: Optional[str] = None) -> None:
        """
        Track a user's interaction with the bot.
        
        Args:
            user_id: Telegram user ID
            first_name: User's first name
            username: Optional username
        """
        try:
            users = self._load_users()
            
            # Update or add user
            if str(user_id) not in users:
                users[str(user_id)] = {
                    "first_name": first_name,
                    "username": username,
                    "first_seen": datetime.now().isoformat(),
                    "last_seen": datetime.now().isoformat(),
                    "interaction_count": 1,
                    "meta": ""  # Add empty meta information object
                }
            else:
                users[str(user_id)].update({
                    "first_name": first_name,
                    "username": username,
                    "last_seen": datetime.now().isoformat(),
                    "interaction_count": users[str(user_id)].get("interaction_count", 0) + 1
                })
                # Ensure meta exists for existing users
                if "meta" not in users[str(user_id)]:
                    users[str(user_id)]["meta"] = ""
            
            self._save_users(users)
            logger.info(f"Tracked user interaction: {user_id} ({first_name})")
            
        except Exception as e:
            logger.error(f"Failed to track user: {e}")
    
    def get_all_users(self) -> List[Dict]:
        """Get all tracked users."""
        try:
            users = self._load_users()
            return [
                {
                    "user_id": user_id,
                    **user_data
                }
                for user_id, user_data in users.items()
            ]
        except Exception as e:
            logger.error(f"Failed to get users: {e}")
            return []
    
    def get_user(self, user_id: int) -> Optional[Dict]:
        """Get a specific user's data."""
        try:
            users = self._load_users()
            user_data = users.get(str(user_id))
            if user_data:
                return {"user_id": user_id, **user_data}
            return None
        except Exception as e:
            logger.error(f"Failed to get user {user_id}: {e}")
            return None
            
    def get_meta(self, user_id: int) -> Dict[str, Any]:
        """Get user meta information."""
        user = self.get_user(user_id)
        if user and "meta" in user:
            return user["meta"]
        return ""
        
    def set_meta(self, user_id: int, meta: Dict[str, Any]) -> None:
        """Set user meta information."""
        try:
            users = self._load_users()
            if str(user_id) in users:
                users[str(user_id)]["meta"] = meta
                self._save_users(users)
                logger.info(f"Updated meta information for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to set meta for user {user_id}: {e}")
            raise
