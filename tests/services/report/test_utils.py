import pytest
from datetime import datetime
import pandas as pd
from services.report.utils import (
    summarize_activities,
    summarize_training_volume,
    summarize_training_intensity,
    summarize_recovery,
    summarize_training_load,
    summarize_vo2max_evolution,
    summarize_readiness_evolution,
    summarize_race_predictions_weekly,
    summarize_hill_score_weekly,
    summarize_endurance_score_weekly,
    _format_activity,
    _format_child_activity,
    _format_hr_zones,
    _extract_intensity_data
)

@pytest.fixture
def sample_activity():
    """Create a sample activity for testing."""
    return {
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
        'hr_zones': [
            {'zone_number': 1, 'secs_in_zone': 1800, 'zone_low_boundary': 100},
            {'zone_number': 2, 'secs_in_zone': 900, 'zone_low_boundary': 120}
        ]
    }

@pytest.fixture
def sample_multisport_activity():
    """Create a sample multisport activity for testing."""
    return {
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
            }
        ]
    }

class TestActivityFormatting:
    """Tests for activity formatting functions."""

    def test_format_activity(self, sample_activity):
        """Test formatting of a single activity."""
        result = _format_activity(sample_activity)
        
        assert "Morning Run" in result
        assert "2023-01-01T08:00:00" in result
        assert "10.00 km" in result
        assert "1.00 hours" in result
        assert "140 bpm" in result
        assert "180 bpm" in result
        assert "500" in result  # calories

    def test_format_activity_with_missing_data(self):
        """Test formatting activity with missing data."""
        activity = {
            'activity_id': 1,
            'activity_type': 'running',
            'activity_name': None,
            'start_time': None,
            'summary': None
        }
        result = _format_activity(activity)
        
        assert "Unknown" in result
        assert "0.00 km" in result
        assert "N/A bpm" in result

    def test_format_multisport_activity(self, sample_multisport_activity):
        """Test formatting of a multisport activity."""
        result = _format_activity(sample_multisport_activity)
        
        assert "Triathlon Training" in result
        assert "30.00 km" in result
        assert "Child Activities" in result
        assert "Swimming" in result
        assert "Cycling" in result

    def test_format_hr_zones(self, sample_activity):
        """Test formatting of heart rate zones."""
        result = _format_hr_zones(sample_activity['hr_zones'])
        
        assert "Zone" in result
        assert "Time (minutes)" in result
        assert "30.0" in result  # 1800 seconds = 30 minutes
        assert "15.0" in result  # 900 seconds = 15 minutes

    def test_format_hr_zones_empty(self):
        """Test formatting of empty heart rate zones."""
        result = _format_hr_zones([])
        assert "No heart rate zone data available" in result

class TestActivitySummarization:
    """Tests for activity summarization functions."""

    def test_summarize_activities(self, sample_activity, sample_multisport_activity):
        """Test summarization of multiple activities."""
        activities = [sample_activity, sample_multisport_activity]
        result = summarize_activities(activities)
        
        assert "Recent Activities Summary" in result
        assert "Overall Statistics" in result
        assert "Total Activities: 2" in result
        assert "40.00 km" in result  # 10km + 30km
        assert "Individual Activities" in result

    def test_summarize_activities_empty(self):
        """Test summarization with no activities."""
        result = summarize_activities([])
        assert "No activities found" in result

    def test_summarize_training_volume(self, sample_activity, sample_multisport_activity):
        """Test training volume summarization."""
        activities = [sample_activity, sample_multisport_activity]
        result = summarize_training_volume(activities)
        
        assert "Weekly Training Volume" in result
        assert "Hours" in result
        assert "Distance (km)" in result
        assert "Activities" in result

    def test_summarize_training_intensity(self, sample_activity):
        """Test training intensity summarization."""
        result = summarize_training_intensity([sample_activity])
        
        assert "Training Intensity Distribution" in result
        assert "Zone 1" in result
        assert "Zone 2" in result
        assert "30.0" in result  # 30 minutes in Zone 1
        assert "15.0" in result  # 15 minutes in Zone 2

class TestMetricsSummarization:
    """Tests for metrics summarization functions."""

    @pytest.fixture
    def sample_recovery_data(self):
        return [{
            'date': '2023-01-01',
            'sleep': {
                'duration': {'total': 8, 'deep': 2, 'light': 4, 'rem': 2},
                'quality': {'overall_score': 85},
                'avg_overnight_hrv': 65,
                'hrv_status': 'BALANCED'
            },
            'stress': {'max_level': 80, 'avg_level': 45}
        }]

    def test_summarize_recovery(self, sample_recovery_data):
        """Test recovery metrics summarization."""
        result = summarize_recovery(sample_recovery_data)
        
        assert "Recovery Metrics" in result
        assert "Sleep (h)" in result
        assert "8.0" in result
        assert "85" in result  # Sleep score
        assert "45" in result  # Avg stress

    @pytest.fixture
    def sample_training_load(self):
        return [{
            'date': '2023-01-01',
            'acute_load': 250,
            'chronic_load': 300,
            'acwr': 0.83
        }]

    def test_summarize_training_load(self, sample_training_load):
        """Test training load summarization."""
        result = summarize_training_load(sample_training_load)
        
        assert "Training Load" in result
        assert "250" in result  # Acute load
        assert "300" in result  # Chronic load
        assert "0.83" in result  # ACWR

    @pytest.fixture
    def sample_vo2max_data(self):
        return [{
            'date': '2023-01-01',
            'value': 50
        }]

    def test_summarize_vo2max_evolution(self, sample_vo2max_data):
        """Test VO2max evolution summarization."""
        result = summarize_vo2max_evolution(sample_vo2max_data)
        
        assert "VO2max Evolution" in result
        assert "50.0" in result

    @pytest.fixture
    def sample_readiness_data(self):
        return [{
            'date': '2023-01-01',
            'score': 85,
            'level': 'GOOD',
            'sleep_score': 90,
            'recovery_time': '12h'
        }]

    def test_summarize_readiness_evolution(self, sample_readiness_data):
        """Test readiness evolution summarization."""
        result = summarize_readiness_evolution(sample_readiness_data)
        
        assert "Training Readiness" in result
        assert "85" in result  # Readiness score
        assert "GOOD" in result
        assert "90" in result  # Sleep score

class TestErrorHandling:
    """Tests for error handling in utility functions."""

    def test_handle_missing_summary(self):
        """Test handling of activity with missing summary."""
        activity = {
            'activity_id': 1,
            'activity_type': 'running',
            'activity_name': 'Test Run',
            'start_time': '2023-01-01T08:00:00'
        }
        result = _format_activity(activity)
        assert "0.00 km" in result
        assert "0.00 hours" in result

    def test_handle_invalid_hr_zones(self):
        """Test handling of invalid heart rate zones."""
        activity = {
            'activity_id': 1,
            'activity_type': 'running',
            'hr_zones': [{'invalid': 'data'}]
        }
        result = _format_activity(activity)
        assert "Error formatting HR zones" in result or "No heart rate zone data available" in result

    def test_handle_invalid_dates(self):
        """Test handling of invalid dates in metrics."""
        data = [{
            'date': 'invalid_date',
            'value': 50
        }]
        result = summarize_vo2max_evolution(data)
        assert "Error" in result or "No valid" in result

    def test_handle_none_values(self):
        """Test handling of None values in metrics."""
        data = [{
            'date': '2023-01-01',
            'score': None,
            'level': None
        }]
        result = summarize_readiness_evolution(data)
        assert "N/A" in result
