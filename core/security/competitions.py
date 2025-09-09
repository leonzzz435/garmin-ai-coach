import logging
from datetime import date

from services.garmin.competition_models import Competition, RacePriority

from .base import SecureStorageBase, StorageError

logger = logging.getLogger(__name__)


class SecureCompetitionManager(SecureStorageBase):

    def __init__(self, user_id: str):
        super().__init__(user_id, "competitions")

    def add_competition(self, competition: Competition) -> None:
        try:
            competitions = self._read() or {}

            comp_dict = {
                "name": competition.name,
                "date": competition.date.isoformat(),
                "race_type": competition.race_type,
                "priority": competition.priority.value,
                "target_time": competition.target_time,
                "location": competition.location,
                "notes": competition.notes,
                "completed": competition.completed,
            }

            competitions[competition.date.isoformat()] = comp_dict
            self._write(competitions)

        except Exception as e:
            raise StorageError(f"Failed to add competition: {str(e)}") from e

    def get_competition(self, competition_date: date) -> Competition | None:
        try:
            competitions = self._read() or {}
            comp_dict = competitions.get(competition_date.isoformat())

            if not comp_dict:
                return None

            return Competition(
                name=comp_dict["name"],
                date=date.fromisoformat(comp_dict["date"]),
                race_type=comp_dict["race_type"],
                priority=RacePriority(comp_dict["priority"]),
                target_time=comp_dict["target_time"],
                location=comp_dict["location"],
                notes=comp_dict["notes"],
                completed=comp_dict["completed"],
            )

        except Exception as e:
            raise StorageError(f"Failed to retrieve competition: {str(e)}") from e

    def get_upcoming_competitions(self, from_date: date | None = None) -> list[Competition]:
        try:
            if from_date is None:
                from_date = date.today()

            competitions = self._read() or {}
            upcoming = [
                Competition(
                    name=comp_dict["name"],
                    date=date.fromisoformat(comp_dict["date"]),
                    race_type=comp_dict["race_type"],
                    priority=RacePriority(comp_dict["priority"]),
                    target_time=comp_dict["target_time"],
                    location=comp_dict["location"],
                    notes=comp_dict["notes"],
                    completed=comp_dict["completed"],
                )
                for comp_dict in competitions.values()
                if date.fromisoformat(comp_dict["date"]) >= from_date and not comp_dict["completed"]
            ]

            # Sort by date
            return sorted(upcoming, key=lambda x: x.date)

        except Exception as e:
            raise StorageError(f"Failed to retrieve upcoming competitions: {str(e)}") from e

    def update_competition(self, competition_date: date, updated_competition: Competition) -> bool:
        try:
            competitions = self._read() or {}

            if competition_date.isoformat() not in competitions:
                return False

            # Remove old entry if date changed
            if competition_date != updated_competition.date:
                del competitions[competition_date.isoformat()]

            # Add updated entry
            competitions[updated_competition.date.isoformat()] = {
                "name": updated_competition.name,
                "date": updated_competition.date.isoformat(),
                "race_type": updated_competition.race_type,
                "priority": updated_competition.priority.value,
                "target_time": updated_competition.target_time,
                "location": updated_competition.location,
                "notes": updated_competition.notes,
                "completed": updated_competition.completed,
            }

            self._write(competitions)
            return True

        except Exception as e:
            raise StorageError(f"Failed to update competition: {str(e)}") from e

    def delete_competition(self, competition_date: date) -> bool:
        try:
            logger.info(f"Attempting to delete competition on {competition_date}")

            # First read current data and make a deep copy
            competitions = self._read() or {}
            logger.debug(f"Current competitions in storage: {list(competitions.keys())}")

            # Convert to string for consistent comparison
            date_key = competition_date.isoformat()
            logger.info(f"Looking for competition with key: {date_key}")

            if date_key not in competitions:
                logger.warning(f"No competition found for date {date_key}")
                return False

            # Store competition details before deletion
            comp_to_delete = dict(competitions[date_key])  # Make a copy
            logger.info(f"Found competition to delete: {comp_to_delete}")

            # Create completely new dict without the competition to delete
            updated_competitions = {}
            for k, v in competitions.items():
                if k != date_key:
                    updated_competitions[k] = dict(v)  # Make copies of values

            logger.debug(f"Competitions after filtering: {list(updated_competitions.keys())}")
            logger.debug(
                f"Original competitions count: {len(competitions)}, Updated count: {len(updated_competitions)}"
            )

            # Write updated competitions back to storage
            self._write(updated_competitions)
            logger.info("Wrote updated competitions to storage")

            # Verify by reading back
            verification_data = self._read() or {}
            if date_key in verification_data:
                logger.error("Competition still exists in storage after deletion")
                logger.debug(f"Current storage state: {list(verification_data.keys())}")
                return False

            # Double check with get_competition
            if self.get_competition(competition_date) is not None:
                logger.error("Competition still retrievable after deletion")
                return False

            logger.info("Competition successfully deleted and verified")
            return True

        except Exception as e:
            error_msg = f"Failed to delete competition: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise StorageError(error_msg) from e
