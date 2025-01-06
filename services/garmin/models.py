from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, List, Optional

import os

class TimeRange(Enum):
    """Time ranges for data extraction"""
    # Values are determined by AI_MODE environment variable
    RECENT = 7 if os.getenv('AI_MODE') == 'development' else 21
    EXTENDED = 14 if os.getenv('AI_MODE') == 'development' else 56

@dataclass
class ExtractionConfig:
    """Configuration for data extraction"""
    activities_range: int = TimeRange.RECENT.value
    metrics_range: int = TimeRange.EXTENDED.value
    include_detailed_activities: bool = True
    include_metrics: bool = True

@dataclass
class UserProfile:
    """User profile data"""
    gender: Optional[str] = None
    weight: Optional[float] = None
    height: Optional[float] = None
    birth_date: Optional[str] = None
    activity_level: Optional[str] = None
    vo2max_running: Optional[float] = None
    vo2max_cycling: Optional[float] = None
    lactate_threshold_pace: Optional[str] = None
    lactate_threshold_heart_rate: Optional[int] = None
    ftp_auto_detected: Optional[bool] = None
    available_training_days: Optional[List[str]] = None
    preferred_long_training_days: Optional[List[str]] = None
    sleep_time: Optional[str] = None
    wake_time: Optional[str] = None

@dataclass
class DailyStats:
    """Daily statistics"""
    date: Optional[str] = None
    total_steps: Optional[int] = None
    total_distance_meters: Optional[float] = None
    total_calories: Optional[int] = None
    active_calories: Optional[int] = None
    bmr_calories: Optional[int] = None
    wellness_start_time: Optional[str] = None
    wellness_end_time: Optional[str] = None
    duration_in_hours: Optional[float] = None
    min_heart_rate: Optional[int] = None
    max_heart_rate: Optional[int] = None
    resting_heart_rate: Optional[int] = None
    average_stress_level: Optional[float] = None
    max_stress_level: Optional[int] = None
    stress_duration_seconds: Optional[int] = None
    sleeping_seconds: Optional[int] = None
    sleeping_hours: Optional[float] = None
    body_battery_highest: Optional[int] = None
    body_battery_lowest: Optional[int] = None
    body_battery_most_recent: Optional[int] = None
    respiration_average: Optional[float] = None
    respiration_highest: Optional[float] = None
    respiration_lowest: Optional[float] = None

@dataclass
class ActivitySummary:
    """Activity summary data"""
    distance: Optional[float] = None
    duration: Optional[int] = None
    moving_duration: Optional[int] = None
    elevation_gain: Optional[float] = None
    elevation_loss: Optional[float] = None
    average_speed: Optional[float] = None
    max_speed: Optional[float] = None
    calories: Optional[int] = None
    average_hr: Optional[int] = None
    max_hr: Optional[int] = None
    training_effect: Optional[float] = None
    anaerobic_training_effect: Optional[float] = None
    training_effect_label: Optional[str] = None
    activity_training_load: Optional[int] = None
    moderate_intensity_minutes: Optional[int] = None
    vigorous_intensity_minutes: Optional[int] = None
    recovery_heart_rate: Optional[int] = None
    begin_potential_stamina: Optional[float] = None
    end_potential_stamina: Optional[float] = None
    min_available_stamina: Optional[float] = None
    difference_body_battery: Optional[int] = None

@dataclass
class WeatherData:
    """Weather data for an activity"""
    temp: Optional[float] = None
    apparent_temp: Optional[float] = None
    relative_humidity: Optional[float] = None
    wind_speed: Optional[float] = None
    weather_type: Optional[str] = None

@dataclass
class HeartRateZone:
    """Heart rate zone data"""
    zone_number: Optional[int] = None
    secs_in_zone: Optional[int] = None
    zone_low_boundary: Optional[int] = None

@dataclass
class Activity:
    """Complete activity data"""
    activity_id: Optional[int] = None
    activity_type: Optional[str] = None
    activity_name: Optional[str] = None
    start_time: Optional[str] = None
    summary: Optional[ActivitySummary] = None
    weather: Optional[WeatherData] = None
    hr_zones: Optional[List[HeartRateZone]] = None
    laps: Optional[List[Dict[str, Any]]] = None  # Complex structure, keeping as Dict for now

@dataclass
class PhysiologicalMarkers:
    """Physiological markers data"""
    resting_heart_rate: Optional[int] = None
    vo2_max: Optional[float] = None
    hrv: Optional[Dict[str, Any]] = None  # Complex nested structure, keeping as Dict for now

@dataclass
class BodyMetrics:
    """Body metrics data"""
    weight: Optional[Dict[str, Any]] = None  # Complex nested structure with historical data
    hydration: Optional[List[Dict[str, Any]]] = None  # Complex structure with daily data

@dataclass
class RecoveryIndicators:
    """Recovery indicators including sleep and stress data"""
    date: Optional[str] = None
    sleep: Optional[Dict[str, Any]] = None  # Complex nested structure
    stress: Optional[Dict[str, Any]] = None  # Complex nested structure

@dataclass
class TrainingStatus:
    """Training status information"""
    vo2_max: Optional[Dict[str, Any]] = None
    training_load_balance: Optional[Dict[str, Any]] = None
    training_status: Optional[Dict[str, Any]] = None
    acute_training_load: Optional[Dict[str, Any]] = None

@dataclass
class GarminData:
    """Complete Garmin data container"""
    user_profile: Optional[UserProfile] = None
    daily_stats: Optional[DailyStats] = None
    recent_activities: Optional[List[Activity]] = None
    all_activities: Optional[List[Activity]] = None
    physiological_markers: Optional[PhysiologicalMarkers] = None
    body_metrics: Optional[BodyMetrics] = None
    recovery_indicators: Optional[List[RecoveryIndicators]] = None
    training_status: Optional[TrainingStatus] = None
    training_readiness: Optional[List[Dict[str, Any]]] = None
    race_predictions: Optional[List[Dict[str, Any]]] = None
    hill_score: Optional[List[Dict[str, Any]]] = None
    endurance_score: Optional[Dict[str, Any]] = None
    endurance_score_history: Optional[List[Dict[str, Any]]] = None
    vo2_max_history: Optional[List[Dict[str, Any]]] = None
    training_load_history: Optional[List[Dict[str, Any]]] = None
