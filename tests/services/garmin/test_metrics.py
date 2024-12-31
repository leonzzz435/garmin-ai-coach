import pytest
from datetime import date
from unittest.mock import MagicMock, patch

from services.garmin.data_extractor import TriathlonCoachDataExtractor
from services.garmin.models import (
    PhysiologicalMarkers, BodyMetrics, RecoveryIndicators,
    TrainingStatus, ExtractionConfig
)

@pytest.fixture
def mock_metrics_responses():
    """Create mock responses for metrics-related API calls"""
    return {
        'rhr': {
            'allMetrics': {
                'metricsMap': {
                    'WELLNESS_RESTING_HEART_RATE': [
                        {'value': 45}
                    ]
                }
            }
        },
        'user_summary': {
            'vo2Max': 50
        },
        'hrv': {
            'hrvSummary': {
                'weeklyAvg': 65,
                'lastNightAvg': 68,
                'lastNight5MinHigh': 75,
                'status': 'BALANCED',
                'baseline': {
                    'lowUpper': 50,
                    'balancedLow': 55,
                    'balancedUpper': 70
                }
            }
        },
        'body_composition': {
            'dateWeightList': [
                {
                    'calendarDate': '2023-01-01',
                    'weight': 75000,  # in grams
                    'sourceType': 'MANUAL'
                },
                {
                    'calendarDate': '2023-01-02',
                    'weight': 74800,
                    'sourceType': 'MANUAL'
                }
            ],
            'totalAverage': {'weight': 74900}
        },
        'hydration': {
            'calendarDate': '2023-01-01',
            'goalInML': 3000,
            'valueInML': 2500,
            'sweatLossInML': 500
        },
        'sleep': {
            'dailySleepDTO': {
                'sleepTimeSeconds': 28800,  # 8 hours
                'deepSleepSeconds': 7200,   # 2 hours
                'lightSleepSeconds': 14400,  # 4 hours
                'remSleepSeconds': 7200,    # 2 hours
                'awakeSleepSeconds': 1800,  # 30 minutes
                'sleepScores': {
                    'overall': {'value': 85},
                    'deepPercentage': {'value': 25},
                    'remPercentage': {'value': 25}
                },
                'restlessMomentsCount': 5,
                'avgOvernightHrv': 65,
                'hrvStatus': 'BALANCED',
                'bodyBatteryChange': 60,
                'restingHeartRate': 45
            }
        },
        'stress': {
            'maxStressLevel': 80,
            'avgStressLevel': 45
        },
        'training_status': {
            'mostRecentVO2Max': {
                'generic': {
                    'vo2MaxValue': 50,
                    'calendarDate': '2023-01-01'
                }
            },
            'mostRecentTrainingLoadBalance': {
                'metricsTrainingLoadBalanceDTOMap': {
                    'key1': {
                        'monthlyLoadAerobicLow': 400,
                        'monthlyLoadAerobicHigh': 600,
                        'monthlyLoadAnaerobic': 200,
                        'trainingBalanceFeedbackPhrase': 'Training load is balanced'
                    }
                }
            },
            'mostRecentTrainingStatus': {
                'latestTrainingStatusData': {
                    'key1': {
                        'trainingStatus': 'PRODUCTIVE',
                        'loadLevelTrend': 'INCREASING',
                        'fitnessTrend': 'IMPROVING',
                        'trainingStatusFeedbackPhrase': 'Your training is productive',
                        'acuteTrainingLoadDTO': {
                            'dailyTrainingLoadAcute': 250,
                            'dailyTrainingLoadChronic': 300,
                            'dailyAcuteChronicWorkloadRatio': 0.83,
                            'acwrStatus': 'OPTIMAL',
                            'acwrStatusFeedback': 'Training load ratio is optimal'
                        }
                    }
                }
            }
        }
    }

@pytest.fixture
def mock_garmin_client(mock_metrics_responses):
    """Create a mock Garmin client with metrics-related responses"""
    client = MagicMock()
    
    client.get_rhr_day.return_value = mock_metrics_responses['rhr']
    client.get_user_summary.return_value = mock_metrics_responses['user_summary']
    client.get_hrv_data.return_value = mock_metrics_responses['hrv']
    client.get_body_composition.return_value = mock_metrics_responses['body_composition']
    client.get_hydration_data.return_value = mock_metrics_responses['hydration']
    client.get_sleep_data.return_value = mock_metrics_responses['sleep']
    client.get_stress_data.return_value = mock_metrics_responses['stress']
    client.get_training_status.return_value = mock_metrics_responses['training_status']
    
    return client

@pytest.fixture
def extractor(mock_garmin_client):
    """Create a DataExtractor instance with mocked client"""
    with patch('services.garmin.data_extractor.GarminConnectClient') as mock_client_class:
        mock_client_class.return_value.client = mock_garmin_client
        extractor = TriathlonCoachDataExtractor('test@example.com', 'password')
        return extractor

class TestMetricsProcessing:
    """Tests for metrics processing methods"""

    def test_get_physiological_markers(self, extractor):
        """Test physiological markers extraction"""
        markers = extractor.get_physiological_markers(
            date(2023, 1, 1),
            date(2023, 1, 7)
        )
        
        assert isinstance(markers, PhysiologicalMarkers)
        assert markers.resting_heart_rate == 45
        assert markers.vo2_max == 50
        assert markers.hrv['weekly_avg'] == 65
        assert markers.hrv['last_night_avg'] == 68
        assert markers.hrv['status'] == 'BALANCED'
        assert markers.hrv['baseline']['balanced_low'] == 55

    def test_get_body_metrics(self, extractor):
        """Test body metrics extraction"""
        metrics = extractor.get_body_metrics(
            date(2023, 1, 1),
            date(2023, 1, 7)
        )
        
        assert isinstance(metrics, BodyMetrics)
        
        # Check weight data
        assert metrics.weight['average'] == 74.9  # Converted to kg
        assert len(metrics.weight['data']) == 2
        assert metrics.weight['data'][0]['weight'] == 75.0  # Converted to kg
        assert metrics.weight['data'][0]['date'] == '2023-01-01'
        
        # Check hydration data
        assert len(metrics.hydration) > 0
        assert metrics.hydration[0]['goal'] == 3.0  # Converted to liters
        assert metrics.hydration[0]['intake'] == 2.5  # Converted to liters
        assert metrics.hydration[0]['sweat_loss'] == 0.5  # Converted to liters

    def test_get_recovery_indicators(self, extractor):
        """Test recovery indicators extraction"""
        indicators = extractor.get_recovery_indicators(
            date(2023, 1, 1),
            date(2023, 1, 7)
        )
        
        assert isinstance(indicators, list)
        assert len(indicators) > 0
        assert isinstance(indicators[0], RecoveryIndicators)
        
        # Check sleep data
        sleep = indicators[0].sleep
        assert sleep['duration']['total'] == 8.0  # Converted to hours
        assert sleep['duration']['deep'] == 2.0
        assert sleep['duration']['light'] == 4.0
        assert sleep['duration']['rem'] == 2.0
        assert sleep['quality']['overall_score'] == 85
        assert sleep['avg_overnight_hrv'] == 65
        assert sleep['hrv_status'] == 'BALANCED'
        
        # Check stress data
        stress = indicators[0].stress
        assert stress['max_level'] == 80
        assert stress['avg_level'] == 45

    def test_get_training_status(self, extractor):
        """Test training status extraction"""
        status = extractor.get_training_status(date(2023, 1, 1))
        
        assert isinstance(status, TrainingStatus)
        
        # Check VO2 Max
        assert status.vo2_max['value'] == 50
        assert status.vo2_max['date'] == '2023-01-01'
        
        # Check training load balance
        assert status.training_load_balance['aerobic_low'] == 400
        assert status.training_load_balance['aerobic_high'] == 600
        assert status.training_load_balance['anaerobic'] == 200
        
        # Check training status
        assert status.training_status['status'] == 'PRODUCTIVE'
        assert status.training_status['load_level_trend'] == 'INCREASING'
        assert status.training_status['fitness_trend'] == 'IMPROVING'
        
        # Check acute training load
        assert status.acute_training_load['acute_load'] == 250
        assert status.acute_training_load['chronic_load'] == 300
        assert status.acute_training_load['acwr'] == 0.83
        assert status.acute_training_load['acwr_status'] == 'OPTIMAL'

    def test_extract_data_with_metrics(self, extractor):
        """Test full data extraction including metrics"""
        data = extractor.extract_data(ExtractionConfig(
            activities_range=7,
            metrics_range=14,
            include_metrics=True
        ))
        
        # Check physiological markers
        assert data.physiological_markers.resting_heart_rate == 45
        assert data.physiological_markers.vo2_max == 50
        
        # Check body metrics
        assert data.body_metrics.weight['average'] == 74.9
        assert len(data.body_metrics.hydration) > 0
        
        # Check recovery indicators
        assert len(data.recovery_indicators) > 0
        assert data.recovery_indicators[0].sleep['quality']['overall_score'] == 85
        
        # Check training status
        assert data.training_status.vo2_max['value'] == 50
        assert data.training_status.training_status['status'] == 'PRODUCTIVE'
