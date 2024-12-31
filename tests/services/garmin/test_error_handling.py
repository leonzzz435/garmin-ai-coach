import pytest
from datetime import date
from unittest.mock import MagicMock, patch

from services.garmin.data_extractor import TriathlonCoachDataExtractor
from services.garmin.models import ExtractionConfig, Activity, GarminData

class TestErrorHandling:
    """Tests for error handling in the data extractor"""

    @pytest.fixture
    def failing_client(self):
        """Create a mock Garmin client that simulates failures"""
        client = MagicMock()
        client.get_user_profile.side_effect = Exception("API Error")
        client.get_stats.side_effect = Exception("API Error")
        client.get_activities_by_date.side_effect = Exception("API Error")
        return client

    @pytest.fixture
    def partial_failing_client(self):
        """Create a mock Garmin client that succeeds for basic calls but fails for details"""
        client = MagicMock()
        
        # Basic calls succeed
        client.get_user_profile.return_value = {
            'userData': {'gender': 'male'},
            'userSleep': {}
        }
        client.get_stats.return_value = {'calendarDate': '2023-01-01'}
        
        # Activity list succeeds but details fail
        client.get_activities_by_date.return_value = [
            {'activityId': 1, 'activityName': 'Test Activity'}
        ]
        client.get_activity.side_effect = Exception("Failed to get activity details")
        client.get_activity_weather.side_effect = Exception("Weather API error")
        client.get_activity_hr_in_timezones.side_effect = Exception("HR zones error")
        
        return client

    @pytest.fixture
    def malformed_client(self):
        """Create a mock Garmin client that returns malformed data"""
        client = MagicMock()
        
        # Missing required fields
        client.get_user_profile.return_value = {'userData': {}}
        client.get_stats.return_value = {}
        
        # Invalid data types
        client.get_activities_by_date.return_value = [
            {
                'activityId': 'not_a_number',
                'activityType': None,
                'summaryDTO': None
            }
        ]
        
        return client

    def test_complete_failure(self):
        """Test behavior when all API calls fail"""
        with patch('services.garmin.data_extractor.GarminConnectClient') as mock_client_class:
            mock_client_class.return_value.client = self.failing_client()
            extractor = TriathlonCoachDataExtractor('test@example.com', 'password')
            
            # Should return a valid GarminData object with None/empty values
            data = extractor.extract_data()
            assert isinstance(data, GarminData)
            assert data.user_profile is None
            assert data.daily_stats is None
            assert data.recent_activities == []

    def test_partial_failure(self, partial_failing_client):
        """Test behavior when some API calls succeed but others fail"""
        with patch('services.garmin.data_extractor.GarminConnectClient') as mock_client_class:
            mock_client_class.return_value.client = partial_failing_client
            extractor = TriathlonCoachDataExtractor('test@example.com', 'password')
            
            data = extractor.extract_data()
            
            # Basic data should be present
            assert data.user_profile is not None
            assert data.user_profile.gender == 'male'
            assert data.daily_stats is not None
            assert data.daily_stats.date == '2023-01-01'
            
            # Activities should be empty due to detail fetch failures
            assert data.recent_activities == []

    def test_malformed_data(self, malformed_client):
        """Test handling of malformed API responses"""
        with patch('services.garmin.data_extractor.GarminConnectClient') as mock_client_class:
            mock_client_class.return_value.client = malformed_client
            extractor = TriathlonCoachDataExtractor('test@example.com', 'password')
            
            data = extractor.extract_data()
            
            # Should handle missing fields gracefully
            assert data.user_profile is not None
            assert data.user_profile.gender is None
            
            # Should handle invalid data types
            assert data.recent_activities == []

    def test_invalid_date_ranges(self):
        """Test handling of invalid date ranges in config"""
        with patch('services.garmin.data_extractor.GarminConnectClient') as mock_client_class:
            extractor = TriathlonCoachDataExtractor('test@example.com', 'password')
            
            # Test with negative ranges
            config = ExtractionConfig(activities_range=-7, metrics_range=-14)
            data = extractor.extract_data(config)
            
            # Should use absolute values of ranges
            ranges = extractor.get_date_ranges(config)
            assert (ranges['activities']['end'] - ranges['activities']['start']).days == 7
            assert (ranges['metrics']['end'] - ranges['metrics']['start']).days == 14

    def test_connection_failure(self):
        """Test handling of connection failures"""
        with patch('services.garmin.data_extractor.GarminConnectClient') as mock_client_class:
            mock_client_class.return_value.connect.side_effect = Exception("Connection failed")
            
            # Should raise the connection error
            with pytest.raises(Exception) as exc_info:
                TriathlonCoachDataExtractor('test@example.com', 'password')
            assert "Connection failed" in str(exc_info.value)

    def test_activity_processing_errors(self, partial_failing_client):
        """Test handling of errors during activity processing"""
        with patch('services.garmin.data_extractor.GarminConnectClient') as mock_client_class:
            mock_client_class.return_value.client = partial_failing_client
            extractor = TriathlonCoachDataExtractor('test@example.com', 'password')
            
            # Test single activity processing
            activity = extractor._process_single_sport_activity({
                'activityId': 1,
                'activityName': 'Test Activity',
                'activityType': {'typeKey': 'running'},
                'summaryDTO': {}
            })
            
            assert isinstance(activity, Activity)
            assert activity.activity_id == 1
            assert activity.activity_type == 'running'
            assert activity.weather is not None  # Should create empty weather object
            assert activity.hr_zones == []  # Should handle missing HR zones
            
            # Test multisport activity with missing child activities
            activity = extractor._process_multisport_activity({
                'activityId': 2,
                'activityName': 'Test Multisport',
                'activityType': {'typeKey': 'multisport'},
                'summaryDTO': {},
                'metadataDTO': {
                    'childIds': [3, 4],
                    'childActivityTypes': ['swimming', 'running']
                }
            })
            
            assert isinstance(activity, Activity)
            assert activity.activity_type == 'multisport'
            assert activity.hr_zones == []
            assert activity.laps == []

    def test_metrics_processing_errors(self, failing_client):
        """Test handling of errors during metrics processing"""
        with patch('services.garmin.data_extractor.GarminConnectClient') as mock_client_class:
            mock_client_class.return_value.client = failing_client
            extractor = TriathlonCoachDataExtractor('test@example.com', 'password')
            
            # Test metrics extraction with failing API calls
            data = extractor.extract_data(ExtractionConfig(include_metrics=True))
            
            assert data.physiological_markers is None
            assert data.body_metrics is None
            assert data.recovery_indicators == []
            assert data.training_status is None
