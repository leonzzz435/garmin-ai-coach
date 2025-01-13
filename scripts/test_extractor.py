from services.garmin.data_extractor import TriathlonCoachDataExtractor
from services.garmin.models import ExtractionConfig
import json
from datetime import datetime, date
from typing import Any

config = ExtractionConfig(
    activities_range=7,
    metrics_range=14,
    include_detailed_activities=True,
    include_metrics=True
)

class GarminEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle Garmin data objects"""
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
    extractor = TriathlonCoachDataExtractor(
        email="l.zajchowski@web.de",
        password="Spider2007!"
    )
    
    # Extract all data with default config (includes all metrics)
    print("Extracting data from Garmin Connect...")
    data = extractor.extract_data(config)
    
    # Save to a timestamped file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"stuff/garmin_data_{timestamp}.json"
    
    print(f"Saving data to {filename}...")
    with open(filename, 'w') as f:
        json.dump(vars(data), f, indent=2, cls=GarminEncoder)
    
    print(f"Data has been saved to {filename}")

if __name__ == "__main__":
    main()
