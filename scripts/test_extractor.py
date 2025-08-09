import sys
from pathlib import Path

# Add the project root directory to the Python path
project_root = Path(__file__).parent.parent  # Go up one level from the scripts directory
sys.path.append(str(project_root))

import json
import logging
from datetime import date, datetime
from typing import Any

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
    # Initialize the data extractor with credentials
    extractor = TriathlonCoachDataExtractor(email="l.zajchowski@web.de", password="Spider2007!")

    # Extract all data with default config (includes all metrics)
    logger.info("Extracting data from Garmin Connect...")
    data = extractor.extract_data(config)

    # Save to a timestamped file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"stuff/garmin_data_{timestamp}.json"

    logger.info(f"Saving data to {filename}...")
    with open(filename, 'w') as f:
        json.dump(vars(data), f, indent=2, cls=GarminEncoder)

    logger.info(f"Data has been saved to {filename}")


if __name__ == "__main__":
    main()
