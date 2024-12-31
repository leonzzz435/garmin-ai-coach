import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from services.garmin.data_extractor import DataExtractor, TriathlonCoachDataExtractor
from services.garmin.models import (
    ExtractionConfig, TimeRange, UserProfile, DailyStats,
    Activity, ActivitySummary, WeatherData, HeartRateZone
)

class TestDataExtractor:
    """Tests for the base DataExtractor class"""

    def test_safe_divide_and_round(self):
        """Test safe division and rounding functionality"""
        # Test normal division
        assert DataExtractor.safe_divide_and_round(10, 2) == 5.0
        assert DataExtractor.safe_divide_and_round(10, 3, 2) == 3.33
        
        # Test with None numerator
        assert DataExtractor.safe_divide_and_round(None, 2) is None
        
        # Test with decimal places
        assert DataExtractor.safe_divide_and_round(10, 3, 1) == 3.3
        assert DataExtractor.safe_divide_and_round(10, 3, 0) == 3.0

    def test_get_date_ranges(self):
        """Test date range calculation"""
        today = date(2023, 1, 1)
        with patch('services.garmin.data_extractor.date') as mock_date:
            mock_date.today.return_value = today
            
            # Test with default config
            config = ExtractionConfig()
            ranges = DataExtractor.get_date_ranges(config)
            
            assert ranges['activities']['end'] == today
            assert ranges['activities']['start'] == today - timedelta(days=TimeRange.RECENT.value)
            assert ranges['metrics']['end'] == today
            assert ranges['metrics']['start'] == today - timedelta(days=TimeRange.EXTENDED.value)
            
            # Test with custom config
            custom_config = ExtractionConfig(
                activities_range=7,
                metrics_range=14
            )
            ranges = DataExtractor.get_date_ranges(custom_config)
            
            assert ranges['activities']['end'] == today
            assert ranges['activities']['start'] == today - timedelta(days=7)
            assert ranges['metrics']['end'] == today
            assert ranges['metrics']['start'] == today - timedelta(days=14)

class TestTriathlonCoachDataExtractor:
    """Tests for the TriathlonCoachDataExtractor class"""
    
    @pytest.fixture
    def mock_garmin_client(self):
        """Create a mock Garmin client with basic responses"""
        client = MagicMock()
        
        # Mock user profile response
        client.get_user_profile.return_value = {
            'userData': {
                'gender': 'male',
                'weight': 75000,  # in grams
                'height': 180,
                'birthDate': '1990-01-01',
                'vo2MaxRunning': 50,
                'vo2MaxCycling': 48
            },
            'userSleep': {
                'sleepTime': '22:00',
                'wakeTime': '06:00'
            }
        }
        
        # Mock daily stats response
        client.get_stats.return_value = {
            'calendarDate': '2023-01-01',
            'totalSteps': 10000,
            'totalDistanceMeters': 8000,
            'totalKilocalories': 2500,
            'activeKilocalories': 800,
            'bmrKilocalories': 1700,
            'wellnessStartTimeLocal': '2023-01-01T00:00:00',
            'wellnessEndTimeLocal': '2023-01-01T23:59:59',
            'durationInMilliseconds': 86400000,  # 24 hours
            'minHeartRate': 45,
            'maxHeartRate': 180,
            'restingHeartRate': 50
        }
        
        return client

    @pytest.fixture
    def extractor(self, mock_garmin_client):
        """Create a DataExtractor instance with mocked client"""
        with patch('services.garmin.data_extractor.GarminConnectClient') as mock_client_class:
            mock_client_class.return_value.client = mock_garmin_client
            extractor = TriathlonCoachDataExtractor('test@example.com', 'password')
            return extractor

    def test_get_user_profile(self, extractor):
        """Test user profile extraction"""
        profile = extractor.get_user_profile()
        
        assert isinstance(profile, UserProfile)
        assert profile.gender == 'male'
        assert profile.weight == 75000  # Original weight in grams
        assert profile.height == 180
        assert profile.birth_date == '1990-01-01'
        assert profile.vo2max_running == 50
        assert profile.vo2max_cycling == 48
        assert profile.sleep_time == '22:00'
        assert profile.wake_time == '06:00'

    def test_get_daily_stats(self, extractor):
        """Test daily stats extraction"""
        stats = extractor.get_daily_stats(date(2023, 1, 1))
        
        assert isinstance(stats, DailyStats)
        assert stats.date == '2023-01-01'
        assert stats.total_steps == 10000
        assert stats.total_distance_meters == 8000
        assert stats.total_calories == 2500
        assert stats.active_calories == 800
        assert stats.bmr_calories == 1700
        assert stats.duration_in_hours == 24.0
        assert stats.min_heart_rate == 45
        assert stats.max_heart_rate == 180
        assert stats.resting_heart_rate == 50

    def test_extract_activity_summary(self, extractor):
        """Test activity summary extraction"""
        raw_summary = {
            'distance': 10000,
            'duration': 3600,
            'movingDuration': 3500,
            'elevationGain': 100,
            'elevationLoss': 100,
            'averageSpeed': 2.78,  # 10 km/h
            'maxSpeed': 4.17,  # 15 km/h
            'calories': 500,
            'averageHR': 140,
            'maxHR': 180,
            'trainingEffect': 3.5,
            'anaerobicTrainingEffect': 2.0
        }
        
        summary = extractor._extract_activity_summary(raw_summary)
        
        assert isinstance(summary, ActivitySummary)
        assert summary.distance == 10000
        assert summary.duration == 3600
        assert summary.moving_duration == 3500
        assert summary.elevation_gain == 100
        assert summary.elevation_loss == 100
        assert summary.average_speed == 2.78
        assert summary.max_speed == 4.17
        assert summary.calories == 500
        assert summary.average_hr == 140
        assert summary.max_hr == 180
        assert summary.training_effect == 3.5
        assert summary.anaerobic_training_effect == 2.0

    def test_extract_weather_data(self, extractor):
        """Test weather data extraction"""
        raw_weather = {
            'temp': 20,
            'apparentTemp': 22,
            'relativeHumidity': 65,
            'windSpeed': 10,
            'weatherTypeDTO': {'desc': 'Partly Cloudy'}
        }
        
        weather = extractor._extract_weather_data(raw_weather)
        
        assert isinstance(weather, WeatherData)
        assert weather.temp == 20
        assert weather.apparent_temp == 22
        assert weather.relative_humidity == 65
        assert weather.wind_speed == 10
        assert weather.weather_type == 'Partly Cloudy'
        
        # Test with None input
        assert isinstance(extractor._extract_weather_data(None), WeatherData)
        
        # Test with missing weather type
        raw_weather['weatherTypeDTO'] = None
        weather = extractor._extract_weather_data(raw_weather)
        assert weather.weather_type is None

    def test_extract_hr_zone_data(self, extractor):
        """Test heart rate zone data extraction"""
        raw_zones = [
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
        ]
        
        zones = extractor._extract_hr_zone_data(raw_zones)
        
        assert len(zones) == 2
        assert all(isinstance(zone, HeartRateZone) for zone in zones)
        
        assert zones[0].zone_number == 1
        assert zones[0].secs_in_zone == 1800
        assert zones[0].zone_low_boundary == 100
        
        assert zones[1].zone_number == 2
        assert zones[1].secs_in_zone == 900
        assert zones[1].zone_low_boundary == 120
        
        # Test with None input
        assert extractor._extract_hr_zone_data(None) == []
        
        # Test with invalid zone data
        assert extractor._extract_hr_zone_data([None, 'invalid']) == []
