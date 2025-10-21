from services.garmin.data_extractor import TriathlonCoachDataExtractor
from services.garmin.models import ActivitySummary


class TestRunningEconomyMetrics:
    """Test suite for running economy and efficiency metrics."""

    def test_activity_summary_with_running_metrics(self):
        """Test creating ActivitySummary with all running economy metrics."""
        summary = ActivitySummary(
            distance=10000.0,  # 10km run
            duration=3600,     # 1 hour
            average_speed=2.78,  # ~10 km/h
            avg_cadence=170,   # 170 steps per minute
            max_cadence=180,   # 180 steps per minute
            avg_ground_contact_time=250.0,  # 250ms
            avg_vertical_oscillation=8.5,   # 8.5cm
            avg_stride_length=1.2,          # 1.2m
            running_economy_score=85.0,     # 85/100
            efficiency_ratio=0.98,          # Good efficiency
        )

        # Verify all running metrics are accessible and correct
        assert summary.avg_cadence == 170
        assert summary.max_cadence == 180
        assert summary.avg_ground_contact_time == 250.0
        assert summary.avg_vertical_oscillation == 8.5
        assert summary.avg_stride_length == 1.2
        assert summary.running_economy_score == 85.0
        assert summary.efficiency_ratio == 0.98

    def test_activity_summary_with_none_running_metrics(self):
        """Test ActivitySummary handles None values for running metrics."""
        summary = ActivitySummary(
            distance=5000.0,
            duration=1800,
            # All running metrics left as None (default)
        )

        # Verify all running metrics default to None
        assert summary.avg_cadence is None
        assert summary.max_cadence is None
        assert summary.avg_ground_contact_time is None
        assert summary.avg_vertical_oscillation is None
        assert summary.avg_stride_length is None
        assert summary.running_economy_score is None
        assert summary.efficiency_ratio is None

    def test_efficiency_ratio_calculation(self):
        """Test efficiency ratio calculation logic."""
        # Test data that would be processed by data extractor
        speed_ms = 2.78  # m/s (10 km/h)
        cadence = 170    # steps per minute
        
        # Efficiency ratio = speed / cadence * 60
        efficiency = speed_ms / cadence * 60
        expected = 2.78 / 170 * 60  # ≈ 0.98
        
        assert abs(efficiency - expected) < 0.01
        assert 0.9 <= efficiency <= 1.2  # Reasonable range for efficiency ratio

    def test_running_metrics_data_types(self):
        """Test that running metrics maintain correct data types."""
        summary = ActivitySummary(
            avg_cadence=170,               # int
            max_cadence=180,               # int
            avg_ground_contact_time=250.0, # float
            avg_vertical_oscillation=8.5,  # float
            avg_stride_length=1.2,         # float
            running_economy_score=85.0,    # float
            efficiency_ratio=0.98,         # float
        )

        # Verify data types
        assert isinstance(summary.avg_cadence, int)
        assert isinstance(summary.max_cadence, int)
        assert isinstance(summary.avg_ground_contact_time, float)
        assert isinstance(summary.avg_vertical_oscillation, float)
        assert isinstance(summary.avg_stride_length, float)
        assert isinstance(summary.running_economy_score, float)
        assert isinstance(summary.efficiency_ratio, float)

    def test_running_metrics_boundaries(self):
        """Test running metrics with edge case values."""
        # Test with very high efficiency
        summary_high_efficiency = ActivitySummary(
            avg_cadence=180,
            avg_ground_contact_time=200.0,  # Very fast ground contact
            avg_vertical_oscillation=6.0,   # Low bounce
            running_economy_score=95.0,     # Excellent score
            efficiency_ratio=1.1,
        )

        assert summary_high_efficiency.avg_cadence == 180
        assert summary_high_efficiency.avg_ground_contact_time == 200.0
        assert summary_high_efficiency.running_economy_score == 95.0

        # Test with lower efficiency
        summary_low_efficiency = ActivitySummary(
            avg_cadence=150,
            avg_ground_contact_time=300.0,  # Slower ground contact
            avg_vertical_oscillation=12.0,  # Higher bounce
            running_economy_score=65.0,     # Lower score
            efficiency_ratio=0.8,
        )

        assert summary_low_efficiency.avg_cadence == 150
        assert summary_low_efficiency.avg_ground_contact_time == 300.0
        assert summary_low_efficiency.running_economy_score == 65.0


class TestDataExtractorRunningMetrics:
    """Test data extractor handling of running metrics."""

    def test_extract_activity_summary_with_running_data(self, monkeypatch):
        """Test data extractor processes running metrics from Garmin API data."""
        # Mock Garmin client
        class MockGarminClient:
            def connect(self, email, password):
                pass
            
            @property
            def client(self):
                return None

        monkeypatch.setattr(
            "services.garmin.data_extractor.GarminConnectClient", 
            MockGarminClient
        )

        extractor = TriathlonCoachDataExtractor("test@example.com", "password")
        
        # Sample Garmin API response with running metrics
        mock_summary = {
            'distance': 10000.0,
            'duration': 3600,
            'averageSpeed': 2.78,
            'avgCadence': 170,
            'maxCadence': 180,
            'avgGroundContactTime': 250.0,
            'avgVerticalOscillation': 8.5,
            'avgStrideLength': 1.2,
            'runningEconomyScore': 85.0,
        }

        # Test the extraction method directly
        activity_summary = extractor._extract_activity_summary(mock_summary)

        # Verify running metrics are extracted correctly
        assert activity_summary.avg_cadence == 170
        assert activity_summary.max_cadence == 180
        assert activity_summary.avg_ground_contact_time == 250.0
        assert activity_summary.avg_vertical_oscillation == 8.5
        assert activity_summary.avg_stride_length == 1.2
        assert activity_summary.running_economy_score == 85.0
        
        # Verify efficiency ratio is calculated
        assert activity_summary.efficiency_ratio is not None
        assert abs(activity_summary.efficiency_ratio - 0.98) < 0.01

    def test_extract_activity_summary_without_running_data(self, monkeypatch):
        """Test data extractor handles missing running metrics gracefully."""
        class MockGarminClient:
            def connect(self, email, password):
                pass
            
            @property
            def client(self):
                return None

        monkeypatch.setattr(
            "services.garmin.data_extractor.GarminConnectClient", 
            MockGarminClient
        )

        extractor = TriathlonCoachDataExtractor("test@example.com", "password")
        
        # Sample Garmin API response without running metrics (e.g., cycling activity)
        mock_summary = {
            'distance': 50000.0,  # 50km bike ride
            'duration': 7200,     # 2 hours
            'averageSpeed': 6.94, # ~25 km/h
            'avgPower': 200.0,    # Power data instead of running metrics
        }

        activity_summary = extractor._extract_activity_summary(mock_summary)

        # Verify running metrics are None when not present
        assert activity_summary.avg_cadence is None
        assert activity_summary.max_cadence is None
        assert activity_summary.avg_ground_contact_time is None
        assert activity_summary.avg_vertical_oscillation is None
        assert activity_summary.avg_stride_length is None
        assert activity_summary.running_economy_score is None
        assert activity_summary.efficiency_ratio is None

    def test_efficiency_ratio_calculation_edge_cases(self, monkeypatch):
        """Test efficiency ratio calculation with edge cases."""
        class MockGarminClient:
            def connect(self, email, password):
                pass
            
            @property
            def client(self):
                return None

        monkeypatch.setattr(
            "services.garmin.data_extractor.GarminConnectClient", 
            MockGarminClient
        )

        extractor = TriathlonCoachDataExtractor("test@example.com", "password")
        
        # Test with missing speed
        mock_summary_no_speed = {
            'avgCadence': 170,
        }
        activity_summary = extractor._extract_activity_summary(mock_summary_no_speed)
        assert activity_summary.efficiency_ratio is None

        # Test with missing cadence
        mock_summary_no_cadence = {
            'averageSpeed': 2.78,
        }
        activity_summary = extractor._extract_activity_summary(mock_summary_no_cadence)
        assert activity_summary.efficiency_ratio is None

        # Test with zero cadence (should not happen in real data)
        mock_summary_zero_cadence = {
            'averageSpeed': 2.78,
            'avgCadence': 0,
        }
        activity_summary = extractor._extract_activity_summary(mock_summary_zero_cadence)
        assert activity_summary.efficiency_ratio is None


class TestRunningMetricsIntegration:
    """Integration tests for running metrics with the AI coaching system."""

    def test_running_metrics_serialization(self):
        """Test that running metrics can be serialized for AI analysis."""
        summary = ActivitySummary(
            avg_cadence=170,
            max_cadence=180,
            avg_ground_contact_time=250.0,
            avg_vertical_oscillation=8.5,
            avg_stride_length=1.2,
            running_economy_score=85.0,
            efficiency_ratio=0.98,
        )

        # Convert to dict (as would happen in AI analysis)
        summary_dict = {
            'avg_cadence': summary.avg_cadence,
            'max_cadence': summary.max_cadence,
            'avg_ground_contact_time': summary.avg_ground_contact_time,
            'avg_vertical_oscillation': summary.avg_vertical_oscillation,
            'avg_stride_length': summary.avg_stride_length,
            'running_economy_score': summary.running_economy_score,
            'efficiency_ratio': summary.efficiency_ratio,
        }

        # Verify all metrics are preserved
        assert summary_dict['avg_cadence'] == 170
        assert summary_dict['running_economy_score'] == 85.0
        assert summary_dict['efficiency_ratio'] == 0.98

    def test_running_metrics_for_ai_analysis(self):
        """Test that running metrics provide useful data for AI coaching analysis."""
        # Simulate different running efficiency scenarios
        efficient_run = ActivitySummary(
            avg_cadence=175,
            avg_ground_contact_time=230.0,
            avg_vertical_oscillation=7.5,
            running_economy_score=90.0,
            efficiency_ratio=1.05,
        )

        inefficient_run = ActivitySummary(
            avg_cadence=155,
            avg_ground_contact_time=280.0,
            avg_vertical_oscillation=11.0,
            running_economy_score=70.0,
            efficiency_ratio=0.85,
        )

        # AI coaches can now analyze these patterns
        assert efficient_run.running_economy_score > inefficient_run.running_economy_score
        assert efficient_run.avg_ground_contact_time < inefficient_run.avg_ground_contact_time
        assert efficient_run.avg_vertical_oscillation < inefficient_run.avg_vertical_oscillation
        assert efficient_run.efficiency_ratio > inefficient_run.efficiency_ratio

        # These differences provide rich data for AI analysis
        efficiency_difference = efficient_run.running_economy_score - inefficient_run.running_economy_score
        assert efficiency_difference == 20.0  # Significant difference for AI to analyze


