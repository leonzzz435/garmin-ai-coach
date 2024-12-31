import pytest
from datetime import datetime, date
from services.report.generator import ReportGenerator
from services.garmin.models import GarminData, UserProfile, DailyStats, Activity

@pytest.fixture
def sample_user_profile():
    """Create a sample user profile for testing."""
    return {
        'gender': 'male',
        'weight': 75000,  # in grams
        'height': 180,
        'birth_date': '1990-01-01',
        'activity_level': 'ACTIVE',
        'vo2max_running': 50,
        'vo2max_cycling': 48,
        'lactate_threshold_speed': None,
        'lactate_threshold_heart_rate': None,
        'ftp_auto_detected': None,
        'available_training_days': ['MONDAY', 'WEDNESDAY', 'FRIDAY', 'SUNDAY'],
        'preferred_long_training_days': ['SUNDAY'],
        'sleep_time': '22:00',
        'wake_time': '06:00'
    }

@pytest.fixture
def sample_activities():
    """Create sample activities for testing."""
    return [
        {
            'activity_id': 1,
            'activity_type': 'running',
            'activity_name': 'Morning Run',
            'start_time': '2023-01-01T08:00:00',
            'summary': {
                'distance': 10000,  # meters
                'duration': 3600,   # seconds
                'moving_duration': 3500,
                'elevation_gain': 100,
                'elevation_loss': 100,
                'average_speed': 2.78,
                'max_speed': 4.17,
                'calories': 500,
                'average_hr': 140,
                'max_hr': 180
            },
            'weather': {
                'temp': 20,
                'apparent_temp': 22,
                'relative_humidity': 65,
                'wind_speed': 10,
                'weather_type': 'Partly Cloudy'
            },
            'hr_zones': [
                {'zone_number': 1, 'secs_in_zone': 1800, 'zone_low_boundary': 100},
                {'zone_number': 2, 'secs_in_zone': 900, 'zone_low_boundary': 120}
            ]
        },
        {
            'activity_id': 2,
            'activity_type': 'multisport',
            'activity_name': 'Triathlon Training',
            'start_time': '2023-01-02T09:00:00',
            'summary': {
                'distance': 30000,
                'duration': 7200,
                'calories': 1000
            },
            'childActivities': [
                {
                    'activity_type': 'swimming',
                    'summary': {
                        'distance': 1500,
                        'duration': 1800,
                        'calories': 300
                    }
                },
                {
                    'activity_type': 'cycling',
                    'summary': {
                        'distance': 20000,
                        'duration': 3600,
                        'calories': 400
                    }
                },
                {
                    'activity_type': 'running',
                    'summary': {
                        'distance': 8500,
                        'duration': 1800,
                        'calories': 300
                    }
                }
            ]
        }
    ]

@pytest.fixture
def sample_metrics():
    """Create sample metrics data for testing."""
    return {
        'recovery_indicators': [
            {
                'date': '2023-01-01',
                'sleep': {
                    'duration': {'total': 8, 'deep': 2, 'light': 4, 'rem': 2},
                    'quality': {'overall_score': 85},
                    'avg_overnight_hrv': 65,
                    'hrv_status': 'BALANCED'
                },
                'stress': {'max_level': 80, 'avg_level': 45}
            }
        ],
        'training_load_history': [
            {
                'date': '2023-01-01',
                'acute_load': 250,
                'chronic_load': 300,
                'acwr': 0.83
            }
        ],
        'vo2_max_history': [
            {
                'date': '2023-01-01',
                'value': 50
            }
        ],
        'training_readiness': [
            {
                'date': '2023-01-01',
                'score': 85,
                'level': 'GOOD',
                'sleep_score': 90,
                'recovery_time': '12h'
            }
        ],
        'race_predictions': [
            {
                'date': '2023-01-01',
                '5k': '20:00',
                '10k': '41:30',
                'half_marathon': '1:32:00',
                'marathon': '3:15:00'
            }
        ],
        'hill_score': [
            {
                'date': '2023-01-01',
                'overall_score': 80,
                'strength_score': 75,
                'endurance_score': 85,
                'classification': 'GOOD'
            }
        ],
        'endurance_score_history': [
            {
                'date': '2023-01-01',
                'overall_score': 75,
                'classification': 'TRAINED'
            }
        ]
    }

@pytest.fixture
def sample_data(sample_user_profile, sample_activities, sample_metrics):
    """Combine all sample data into a complete dataset."""
    return {
        'user_profile': sample_user_profile,
        'daily_stats': {
            'date': '2023-01-01',
            'total_steps': 10000,
            'total_distance_meters': 8000,
            'total_calories': 2500
        },
        'recent_activities': sample_activities,
        **sample_metrics
    }

class TestReportGenerator:
    """Tests for the ReportGenerator class."""

    def test_init_with_dict(self, sample_data):
        """Test initialization with dictionary data."""
        generator = ReportGenerator(sample_data)
        assert generator.data == sample_data

    def test_init_with_garmin_data(self, sample_data):
        """Test initialization with GarminData object."""
        garmin_data = GarminData(
            user_profile=UserProfile(**sample_data['user_profile']),
            daily_stats=DailyStats(**sample_data['daily_stats']),
            recent_activities=sample_data['recent_activities'],
            recovery_indicators=sample_data['recovery_indicators'],
            training_load_history=sample_data['training_load_history'],
            vo2_max_history=sample_data['vo2_max_history'],
            training_readiness=sample_data['training_readiness'],
            race_predictions=sample_data['race_predictions'],
            hill_score=sample_data['hill_score'],
            endurance_score_history=sample_data['endurance_score_history']
        )
        generator = ReportGenerator(garmin_data)
        assert isinstance(generator.data, dict)

    def test_generate_activities_report(self, sample_data):
        """Test generation of activities report."""
        generator = ReportGenerator(sample_data)
        report = generator.generate_activities_report()
        
        # Check for key sections
        assert "# Athlete Profile" in report
        assert "# Recent Activities Summary" in report
        assert "Morning Run" in report
        assert "Triathlon Training" in report
        
        # Check for activity details
        assert "10.00 km" in report  # First activity distance
        assert "30.00 km" in report  # Second activity distance
        assert "Heart Rate Zones" in report
        assert "Child Activities" in report

    def test_generate_metrics_report(self, sample_data):
        """Test generation of metrics report."""
        generator = ReportGenerator(sample_data)
        report = generator.generate_metrics_report()
        
        # Check for key sections
        assert "# Performance Metrics" in report
        assert "## Training Intensity" in report
        assert "## Recovery Metrics" in report
        assert "## Training Load" in report
        assert "## VO2max Evolution" in report
        
        # Check for specific metrics
        assert "85" in report  # Sleep score
        assert "GOOD" in report  # Training readiness level
        assert "20:00" in report  # 5k prediction

    def test_generate_full_report(self, sample_data):
        """Test generation of full report."""
        generator = ReportGenerator(sample_data)
        report = generator.generate_full_report()
        
        # Check that all sections are included
        assert "# Athlete Profile" in report
        assert "# Recent Activities Summary" in report
        assert "# Performance Metrics" in report
        assert "# Training Status" in report
        assert "# Performance Predictions and Scores" in report

    def test_error_handling(self):
        """Test handling of invalid or missing data."""
        # Test with empty data
        generator = ReportGenerator({})
        report = generator.generate_full_report()
        assert "No activities found" in report or "No valid" in report
        
        # Test with partial data
        partial_data = {'user_profile': {'gender': 'male'}}
        generator = ReportGenerator(partial_data)
        report = generator.generate_full_report()
        assert "male" in report
        assert "No activities found" in report or "No valid" in report
