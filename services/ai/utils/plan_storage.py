import logging
from abc import ABC, abstractmethod
from pathlib import Path

logger = logging.getLogger(__name__)


def _as_safe_filename(value: str) -> str:
    return "".join(char for char in value if char.isalnum() or char in ("_", "-"))


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
        return self._get_user_dir(user_id) / f"{_as_safe_filename(plan_type)}.md"

    def load_plan(self, user_id: str, plan_type: str) -> str | None:
        try:
            plan_path = self._get_plan_path(user_id, plan_type)
            if plan_path.exists():
                logger.info("Loading %s for user %s from %s", plan_type, user_id, plan_path)
                return plan_path.read_text(encoding="utf-8")
            return None
        except OSError:
            logger.exception("IO Error loading %s for user %s", plan_type, user_id)
            return None
        except Exception:
            logger.exception("Unexpected error loading %s for user %s", plan_type, user_id)
            return None

    def save_plan(self, user_id: str, plan_type: str, content: str) -> None:
        if not content:
            logger.warning("Attempted to save empty content for %s (user: %s)", plan_type, user_id)
            return

        try:
            plan_path = self._get_plan_path(user_id, plan_type)
            plan_path.write_text(content, encoding="utf-8")
            logger.info("Saved %s for user %s to %s", plan_type, user_id, plan_path)
        except OSError:
            logger.exception("IO Error saving %s for user %s", plan_type, user_id)
        except Exception:
            logger.exception("Unexpected error saving %s for user %s", plan_type, user_id)
