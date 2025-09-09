import json
import logging
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from services.garmin.data_extractor import TriathlonCoachDataExtractor
from services.garmin.models import ExtractionConfig

logger = logging.getLogger(__name__)

config = ExtractionConfig(
    activities_range=7, metrics_range=14, include_detailed_activities=True, include_metrics=True
)


class GarminEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, date):
            return obj.isoformat()
        # Handle any object with __dict__ attribute (our model classes)
        if hasattr(obj, '__dict__'):
            return obj.__dict__
        # Handle lists of objects
        if isinstance(obj, list):
            return [self.default(item) for item in obj]
        return super().default(obj)


def main():
    load_dotenv()
    email = os.getenv("GARMIN_EMAIL")
    password = os.getenv("GARMIN_PASSWORD")
    if not email or not password:
        raise ValueError("Set GARMIN_EMAIL and GARMIN_PASSWORD in environment or .env file")
    extractor = TriathlonCoachDataExtractor(email=email, password=password)

    logger.info("Extracting data from Garmin Connect...")
    data = extractor.extract_data(config)

    # Save to a timestamped file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    export_dir = Path("data/exports")
    export_dir.mkdir(parents=True, exist_ok=True)
    filename = export_dir / f"garmin_data_{timestamp}.json"

    logger.info(f"Saving data to {filename}...")
    with open(filename, 'w') as f:
        json.dump(vars(data), f, indent=2, cls=GarminEncoder)

    logger.info(f"Data has been saved to {filename}")


if __name__ == "__main__":
    main()
