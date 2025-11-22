import logging
from abc import ABC, abstractmethod
from pathlib import Path

logger = logging.getLogger(__name__)

class PlanStorage(ABC):
    
    @abstractmethod
    def load_plan(self, user_id: str, plan_type: str) -> str | None:
        pass

    @abstractmethod
    def save_plan(self, user_id: str, plan_type: str, content: str) -> None:
        pass

class FilePlanStorage(PlanStorage):

    def __init__(self, base_dir: str = "data/storage"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
    def _get_user_dir(self, user_id: str) -> Path:
        user_dir = self.base_dir / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir
        
    def _get_plan_path(self, user_id: str, plan_type: str) -> Path:
        # Sanitize plan_type to avoid path traversal or weird filenames
        safe_plan_type = "".join(c for c in plan_type if c.isalnum() or c in ('_', '-'))
        return self._get_user_dir(user_id) / f"{safe_plan_type}.md"

    def load_plan(self, user_id: str, plan_type: str) -> str | None:
        try:
            plan_path = self._get_plan_path(user_id, plan_type)
            if plan_path.exists():
                logger.info(f"Loading {plan_type} for user {user_id} from {plan_path}")
                return plan_path.read_text(encoding="utf-8")
            return None
        except OSError as e:
            logger.error(f"IO Error loading {plan_type} for user {user_id}: {e}", exc_info=True)
            return None
        except Exception as e:
            logger.error(f"Unexpected error loading {plan_type} for user {user_id}: {e}", exc_info=True)
            return None

    def save_plan(self, user_id: str, plan_type: str, content: str) -> None:
        if not content:
            logger.warning(f"Attempted to save empty content for {plan_type} (user: {user_id})")
            return
            
        try:
            plan_path = self._get_plan_path(user_id, plan_type)
            plan_path.write_text(content, encoding="utf-8")
            logger.info(f"Saved {plan_type} for user {user_id} to {plan_path}")
        except OSError as e:
            logger.error(f"IO Error saving {plan_type} for user {user_id}: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Unexpected error saving {plan_type} for user {user_id}: {e}", exc_info=True)
