"""Garmin Connect data extraction service.

This package provides functionality for interacting with Garmin Connect,
extracting activity data, and processing it for triathlon coaching purposes.
"""

from .client import GarminConnectClient
from .data_extractor import DataExtractor, TriathlonCoachDataExtractor
from .models import (
    TimeRange,
    ExtractionConfig,
    UserProfile,
    DailyStats,
    Activity,
    ActivitySummary,
    WeatherData,
    HeartRateZone,
    PhysiologicalMarkers,
    BodyMetrics,
    RecoveryIndicators,
    TrainingStatus,
    GarminData
)

__all__ = [
    'GarminConnectClient',
    'DataExtractor',
    'TriathlonCoachDataExtractor',
    'TimeRange',
    'ExtractionConfig',
    'UserProfile',
    'DailyStats',
    'Activity',
    'ActivitySummary',
    'WeatherData',
    'HeartRateZone',
    'PhysiologicalMarkers',
    'BodyMetrics',
    'RecoveryIndicators',
    'TrainingStatus',
    'GarminData'
]
