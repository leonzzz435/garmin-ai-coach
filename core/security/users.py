import json
import logging
from datetime import datetime
from pathlib import Path

# Configure logging
logger = logging.getLogger(__name__)


class UserTracker:

    def __init__(self):
        self.storage_dir = Path.home() / '.garmin_bot' / 'users'
        self.users_file = self.storage_dir / 'users.json'
        self._setup_storage()

    def _setup_storage(self) -> None:
        try:
            # Create directory if it doesn't exist
            self.storage_dir.mkdir(parents=True, exist_ok=True)

            # Create users file if it doesn't exist
            if not self.users_file.exists():
                self._save_users({})

        except Exception as e:
            logger.error(f"Failed to setup user storage: {e}")
            raise

    def _load_users(self) -> dict:
        try:
            if self.users_file.exists():
                return json.loads(self.users_file.read_text())
            return {}
        except Exception as e:
            logger.error(f"Failed to load users: {e}")
            return {}

    def _save_users(self, users: dict) -> None:
        try:
            self.users_file.write_text(json.dumps(users, indent=2))
        except Exception as e:
            logger.error(f"Failed to save users: {e}")
            raise

    def track_user(self, user_id: int, first_name: str, username: str | None = None) -> None:
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
                }
            else:
                users[str(user_id)].update(
                    {
                        "first_name": first_name,
                        "username": username,
                        "last_seen": datetime.now().isoformat(),
                        "interaction_count": users[str(user_id)].get("interaction_count", 0) + 1,
                    }
                )

            self._save_users(users)
            logger.info(f"Tracked user interaction: {user_id} ({first_name})")

        except Exception as e:
            logger.error(f"Failed to track user: {e}")

    def get_all_users(self) -> list[dict]:
        try:
            users = self._load_users()
            return [{"user_id": user_id, **user_data} for user_id, user_data in users.items()]
        except Exception as e:
            logger.error(f"Failed to get users: {e}")
            return []

    def get_user(self, user_id: int) -> dict | None:
        try:
            users = self._load_users()
            user_data = users.get(str(user_id))
            if user_data:
                return {"user_id": user_id, **user_data}
            return None
        except Exception as e:
            logger.error(f"Failed to get user {user_id}: {e}")
            return None
