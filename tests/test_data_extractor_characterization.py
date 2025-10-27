
from datetime import date
from unittest.mock import Mock, patch

import pytest

from services.garmin.data_extractor import DataExtractor, TriathlonCoachDataExtractor
from services.garmin.models import Activity, ActivitySummary, ExtractionConfig


class TestDataExtractorCharacterization:
    
    def test_safe_divide_and_round_normal_case(self):
        result = DataExtractor.safe_divide_and_round(100.0, 3.0, 2)
        assert result == 33.33
        
    def test_safe_divide_and_round_none_input(self):
        result = DataExtractor.safe_divide_and_round(None, 3.0, 2)
        assert result is None
        
    def test_extract_start_time_from_summary(self):
        activity_data = {
            'summaryDTO': {
                'startTimeLocal': '2025-01-01T10:00:00'
            }
        }
        result = DataExtractor.extract_start_time(activity_data)
        assert result == '2025-01-01T10:00:00'
        
    def test_extract_start_time_fallback_chain(self):
        activity_data = {
            'startTimeLocal': '2025-01-01T11:00:00'
        }
        result = DataExtractor.extract_start_time(activity_data)
        assert result == '2025-01-01T11:00:00'
        
    def test_extract_activity_type_from_nested_dto(self):
        activity_data = {
            'activityType': {
                'typeKey': 'cycling'
            }
        }
        result = DataExtractor.extract_activity_type(activity_data)
        assert result == 'cycling'
        
    def test_extract_activity_type_fallback_unknown(self):
        activity_data = {}
        result = DataExtractor.extract_activity_type(activity_data)
        assert result == 'unknown'
        
    def test_convert_lactate_threshold_speed_conversion(self):
        result = DataExtractor.convert_lactate_threshold_speed(10.0)
        assert result == 100.0  # 10 AU * 10 = 100 m/s
        
    def test_convert_lactate_threshold_speed_none_input(self):
        result = DataExtractor.convert_lactate_threshold_speed(None)
        assert result is None
        
    def test_get_date_ranges_calculation(self):
        ranges = DataExtractor.get_date_ranges(ExtractionConfig(activities_range=21, metrics_range=56))
        
        assert "activities" in ranges
        assert "metrics" in ranges
        assert isinstance(ranges["activities"]["start"], date)
        assert isinstance(ranges["activities"]["end"], date)


class TestTriathlonCoachDataExtractorCharacterization:
    
    @patch('services.garmin.data_extractor.GarminConnectClient')
    def test_initialization_connects_to_garmin(self, mock_client):
        mock_instance = Mock()
        mock_client.return_value = mock_instance
        
        TriathlonCoachDataExtractor("test@example.com", "password")
        
        mock_client.assert_called_once()
        mock_instance.connect.assert_called_once_with("test@example.com", "password")
        
    @patch("services.garmin.data_extractor.GarminConnectClient")
    def test_extract_data_base_data_always_included(self, mock_client):
        mock_instance = Mock()
        mock_client.return_value = mock_instance
        extractor = TriathlonCoachDataExtractor("test@example.com", "password")
        
        mock_instance.client.get_user_profile.return_value = {
            "userData": {"gender": "male", "weight": 70000},
            "userSleep": {"sleepTime": "22:00"}
        }
        mock_instance.client.get_stats.return_value = {
            "calendarDate": "2025-01-01",
            "totalSteps": 10000
        }
        mock_instance.client.get_sleep_data.return_value = {
            "dailySleepDTO": {"sleepTimeSeconds": 28800}
        }
        
        result = extractor.extract_data(ExtractionConfig(include_detailed_activities=False, include_metrics=False))
        
        assert hasattr(result, "user_profile")
        assert hasattr(result, "daily_stats")
        assert result.user_profile.gender == "male"
        assert result.daily_stats.total_steps == 10000
        
    def test_activity_summary_extraction_structure(self):
        result = TriathlonCoachDataExtractor.__new__(TriathlonCoachDataExtractor)._extract_activity_summary({
            "distance": 10000.0,
            "duration": 3600,
            "averageSpeed": 2.78,
            "maxSpeed": 5.0,
            "calories": 400,
            "averageHR": 150,
            "maxHR": 180,
            "avgPower": 250,
            "maxPower": 400
        })
        
        assert isinstance(result, ActivitySummary)
        assert result.distance == 10000.0
        assert result.duration == 3600
        assert result.avg_power == 250
        assert result.max_power == 400
        
    def test_weather_data_extraction_none_input(self):
        extractor = TriathlonCoachDataExtractor.__new__(TriathlonCoachDataExtractor)
        
        result = extractor._extract_weather_data(None)
        
        assert result.temp is None
        assert result.apparent_temp is None
        assert result.relative_humidity is None
        assert result.wind_speed is None
        assert result.weather_type is None


@pytest.fixture
def mock_garmin_client():
    with patch("services.garmin.data_extractor.GarminConnectClient") as mock:
        mock_instance = Mock()
        mock.return_value = mock_instance
        yield mock_instance


class TestDataExtractorIntegrationBehavior:
    
    def test_multisport_activity_processing_structure(self, mock_garmin_client):
        mock_garmin_client.client.get_activity.side_effect = [
            {"activityId": 12346, "activityName": "Swim Leg", "summaryDTO": {"distance": 1500.0, "duration": 1800}},
            {"activityId": 12347, "activityName": "Bike Leg", "summaryDTO": {"distance": 40000.0, "duration": 3600, "avgPower": 200}},
            {"activityId": 12348, "activityName": "Run Leg", "summaryDTO": {"distance": 10000.0, "duration": 2400}}
        ]
        mock_garmin_client.client.get_activity_details.return_value = {}
        mock_garmin_client.client.get_activity_weather.return_value = None
        
        result = TriathlonCoachDataExtractor("test@example.com", "password")._process_multisport_activity({
            "activityId": 12345,
            "activityName": "Morning Triathlon",
            "isMultiSportParent": True,
            "summaryDTO": {"distance": 15000.0, "duration": 5400},
            "metadataDTO": {"childIds": [12346, 12347, 12348], "childActivityTypes": ["swimming", "cycling", "running"]}
        })
        
        assert isinstance(result, Activity)
        assert result.activity_type == "multisport"
        assert len(result.laps) == 3
        assert result.laps[0]["activityType"] == "swimming"
        assert result.laps[1]["activityType"] == "cycling"
        assert result.laps[2]["activityType"] == "running"
        
    def test_cycling_power_data_extraction_priority(self):
        result = TriathlonCoachDataExtractor.__new__(TriathlonCoachDataExtractor)._process_single_sport_activity({
            "activityId": 123,
            "summaryDTO": {"avgPower": 250, "normPower": 260},
            "averagePower": 240,
            "normalizedPower": 250
        })
        
        assert result.summary.avg_power == 250
        assert result.summary.normalized_power == 260