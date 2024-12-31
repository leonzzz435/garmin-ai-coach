import pytest
from datetime import date
from unittest.mock import MagicMock, patch

from services.garmin.data_extractor import TriathlonCoachDataExtractor
from services.garmin.models import Activity, ExtractionConfig

@pytest.fixture
def mock_activity_responses():
    """Create mock responses for activity-related API calls"""
    return {
        'single_activity': {
            'activityId': 1234567890,
            'activityName': 'Morning Run',
            'activityType': {'typeKey': 'running'},
            'summaryDTO': {
                'startTimeLocal': '2023-01-01T08:00:00',
                'distance': 10000,
                'duration': 3600,
                'movingDuration': 3500,
                'elevationGain': 100,
                'elevationLoss': 100,
                'averageSpeed': 2.78,
                'maxSpeed': 4.17,
                'calories': 500,
                'averageHR': 140,
                'maxHR': 180,
                'trainingEffect': 3.5,
                'anaerobicTrainingEffect': 2.0
            }
        },
        'multisport_activity': {
            'activityId': 9876543210,
            'activityName': 'Triathlon Race',
            'activityType': {'typeKey': 'multisport'},
            'summaryDTO': {
                'startTimeLocal': '2023-01-01T07:00:00',
                'distance': 51500,  # Olympic distance
                'duration': 10800,  # 3 hours
                'calories': 2000
            },
            'metadataDTO': {
                'childIds': [1111, 2222, 3333],
                'childActivityTypes': ['swimming', 'cycling', 'running']
            }
        },
        'child_activities': {
            1111: {  # Swim
                'activityId': 1111,
                'summaryDTO': {
                    'distance': 1500,
                    'duration': 1800,
                    'averageSpeed': 1.2,
                    'maxSpeed': 1.5,
                    'calories': 400
                }
            },
            2222: {  # Bike
                'activityId': 2222,
                'summaryDTO': {
                    'distance': 40000,
                    'duration': 4800,
                    'averageSpeed': 8.33,
                    'maxSpeed': 12.5,
                    'calories': 1000
                }
            },
            3333: {  # Run
                'activityId': 3333,
                'summaryDTO': {
                    'distance': 10000,
                    'duration': 3600,
                    'averageSpeed': 2.78,
                    'maxSpeed': 3.33,
                    'calories': 600
                }
            }
        },
        'weather': {
            'temp': 20,
            'apparentTemp': 22,
            'relativeHumidity': 65,
            'windSpeed': 10,
            'weatherTypeDTO': {'desc': 'Partly Cloudy'}
        },
        'hr_zones': [
            {
                'zoneNumber': 1,
                'secsInZone': 1800,
                'zoneLowBoundary': 100
            },
            {
                'zoneNumber': 2,
                'secsInZone': 900,
                'zoneLowBoundary': 120
            }
        ],
        'laps': {
            'lapDTOs': [
                {
                    'startTimeGMT': '2023-01-01T08:00:00Z',
                    'distance': 1000,
                    'duration': 300,
                    'elevationGain': 10,
                    'elevationLoss': 10,
                    'averageSpeed': 3.33,
                    'maxSpeed': 4.17,
                    'averageHR': 140,
                    'maxHR': 160,
                    'calories': 50,
                    'intensityType': 'ACTIVE'
                }
            ]
        }
    }

@pytest.fixture
def mock_garmin_client(mock_activity_responses):
    """Create a mock Garmin client with activity-related responses"""
    client = MagicMock()
    
    def get_activity(activity_id):
        if activity_id in mock_activity_responses['child_activities']:
            return mock_activity_responses['child_activities'][activity_id]
        elif activity_id == 1234567890:
            return mock_activity_responses['single_activity']
        elif activity_id == 9876543210:
            return mock_activity_responses['multisport_activity']
        return None
        
    client.get_activities_by_date.return_value = [
        mock_activity_responses['single_activity'],
        mock_activity_responses['multisport_activity']
    ]
    client.get_activity = MagicMock(side_effect=get_activity)
    client.get_activity_weather.return_value = mock_activity_responses['weather']
    client.get_activity_hr_in_timezones.return_value = mock_activity_responses['hr_zones']
    client.get_activity_splits.return_value = mock_activity_responses['laps']
    
    return client

@pytest.fixture
def extractor(mock_garmin_client):
    """Create a DataExtractor instance with mocked client"""
    with patch('services.garmin.data_extractor.GarminConnectClient') as mock_client_class:
        mock_client_class.return_value.client = mock_garmin_client
        extractor = TriathlonCoachDataExtractor('test@example.com', 'password')
        return extractor

class TestActivityProcessing:
    """Tests for activity processing methods"""

    def test_process_single_sport_activity(self, extractor, mock_activity_responses):
        """Test processing of a single sport activity"""
        activity = extractor._process_single_sport_activity(
            mock_activity_responses['single_activity']
        )
        
        assert isinstance(activity, Activity)
        assert activity.activity_id == 1234567890
        assert activity.activity_type == 'running'
        assert activity.activity_name == 'Morning Run'
        assert activity.start_time == '2023-01-01T08:00:00'
        
        # Check summary
        assert activity.summary.distance == 10000
        assert activity.summary.duration == 3600
        assert activity.summary.moving_duration == 3500
        assert activity.summary.average_speed == 2.78
        assert activity.summary.max_speed == 4.17
        
        # Check weather
        assert activity.weather.temp == 20
        assert activity.weather.apparent_temp == 22
        assert activity.weather.weather_type == 'Partly Cloudy'
        
        # Check HR zones
        assert len(activity.hr_zones) == 2
        assert activity.hr_zones[0].zone_number == 1
        assert activity.hr_zones[0].secs_in_zone == 1800
        
        # Check laps
        assert len(activity.laps) == 1
        assert activity.laps[0]['distance'] == 1.0  # Converted to km
        assert activity.laps[0]['duration'] == 5.0  # Converted to minutes

    def test_process_multisport_activity(self, extractor, mock_activity_responses):
        """Test processing of a multisport activity"""
        activity = extractor._process_multisport_activity(
            mock_activity_responses['multisport_activity']
        )
        
        assert isinstance(activity, Activity)
        assert activity.activity_id == 9876543210
        assert activity.activity_type == 'multisport'
        assert activity.activity_name == 'Triathlon Race'
        assert activity.start_time == '2023-01-01T07:00:00'
        
        # Check summary
        assert activity.summary.distance == 51500
        assert activity.summary.duration == 10800
        assert activity.summary.calories == 2000
        
        # Check weather
        assert activity.weather.temp == 20
        assert activity.weather.apparent_temp == 22
        assert activity.weather.weather_type == 'Partly Cloudy'
        
        # Multisport activities don't have overall HR zones or laps
        assert activity.hr_zones == []
        assert activity.laps == []

    def test_get_recent_activities(self, extractor):
        """Test fetching and processing of recent activities"""
        activities = extractor.get_recent_activities(
            date(2023, 1, 1),
            date(2023, 1, 7)
        )
        
        assert len(activities) == 2
        assert all(isinstance(activity, Activity) for activity in activities)
        
        # Check single sport activity
        run = activities[0]
        assert run.activity_type == 'running'
        assert run.activity_name == 'Morning Run'
        
        # Check multisport activity
        tri = activities[1]
        assert tri.activity_type == 'multisport'
        assert tri.activity_name == 'Triathlon Race'

    def test_extract_data_with_activities(self, extractor):
        """Test full data extraction including activities"""
        data = extractor.extract_data(ExtractionConfig(
            activities_range=7,
            metrics_range=14,
            include_detailed_activities=True
        ))
        
        assert len(data.recent_activities) == 2
        assert all(isinstance(activity, Activity) for activity in data.recent_activities)
        
        # Verify activities are properly processed
        run = data.recent_activities[0]
        assert run.activity_type == 'running'
        assert run.activity_name == 'Morning Run'
        assert run.summary.distance == 10000
        
        tri = data.recent_activities[1]
        assert tri.activity_type == 'multisport'
        assert tri.activity_name == 'Triathlon Race'
        assert tri.summary.distance == 51500
