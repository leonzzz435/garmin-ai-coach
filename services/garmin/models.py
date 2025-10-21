import os
from dataclasses import dataclass
from enum import Enum
from typing import Any


class TimeRange(Enum):
    # Values are determined by AI_MODE environment variable
    RECENT = 7 if os.getenv('AI_MODE') == 'development' else 21
    EXTENDED = 14 if os.getenv('AI_MODE') == 'development' else 56


@dataclass
class ExtractionConfig:
    activities_range: int = TimeRange.RECENT.value
    metrics_range: int = TimeRange.EXTENDED.value
    include_detailed_activities: bool = True
    include_metrics: bool = True
    include_mindfulness: bool = True


@dataclass
class UserProfile:
    gender: str | None = None
    weight: float | None = None
    height: float | None = None
    birth_date: str | None = None
    activity_level: str | None = None
    vo2max_running: float | None = None
    vo2max_cycling: float | None = None
    lactate_threshold_speed: float | None = None  # Speed in m/s
    lactate_threshold_heart_rate: int | None = None
    ftp_auto_detected: bool | None = None
    available_training_days: list[str] | None = None
    preferred_long_training_days: list[str] | None = None
    sleep_time: str | None = None
    wake_time: str | None = None


@dataclass
class DailyStats:
    date: str | None = None
    total_steps: int | None = None
    total_distance_meters: float | None = None
    total_calories: int | None = None
    active_calories: int | None = None
    bmr_calories: int | None = None
    wellness_start_time: str | None = None
    wellness_end_time: str | None = None
    duration_in_hours: float | None = None
    min_heart_rate: int | None = None
    max_heart_rate: int | None = None
    resting_heart_rate: int | None = None
    average_stress_level: float | None = None
    max_stress_level: int | None = None
    stress_duration_seconds: int | None = None
    sleeping_seconds: int | None = None
    sleeping_hours: float | None = None
    respiration_average: float | None = None
    respiration_highest: float | None = None
    respiration_lowest: float | None = None


@dataclass
class ActivitySummary:
    distance: float | None = None
    duration: int | None = None
    moving_duration: int | None = None
    elevation_gain: float | None = None
    elevation_loss: float | None = None
    average_speed: float | None = None
    max_speed: float | None = None
    calories: int | None = None
    average_hr: int | None = None
    max_hr: int | None = None
    min_hr: int | None = None
    activity_training_load: int | None = None
    moderate_intensity_minutes: int | None = None
    vigorous_intensity_minutes: int | None = None
    recovery_heart_rate: int | None = None
    # Respiration (for meditation/mindfulness-capable activities)
    avg_respiration_rate: float | None = None
    min_respiration_rate: float | None = None
    max_respiration_rate: float | None = None
    # Stress (for meditation/mindfulness-capable activities)
    start_stress: float | None = None
    end_stress: float | None = None
    avg_stress: float | None = None
    max_stress: float | None = None
    difference_stress: float | None = None
    # Power-related fields for cycling activities
    avg_power: float | None = None
    max_power: float | None = None
    normalized_power: float | None = None
    training_stress_score: float | None = None
    intensity_factor: float | None = None
    avg_cadence: int | None = None  # Steps per minute
    max_cadence: int | None = None
    avg_ground_contact_time: float | None = None  # Milliseconds
    avg_vertical_oscillation: float | None = None  # Centimeters
    avg_stride_length: float | None = None  # Meters
    running_economy_score: float | None = None  # 0-100 scale
    efficiency_ratio: float | None = None  # Speed/cadence ratio for efficiency


@dataclass
class WeatherData:
    temp: float | None = None
    apparent_temp: float | None = None
    relative_humidity: float | None = None
    wind_speed: float | None = None
    weather_type: str | None = None


@dataclass
class HeartRateZone:
    zone_number: int | None = None
    secs_in_zone: int | None = None
    zone_low_boundary: int | None = None


@dataclass
class Activity:
    activity_id: int | None = None
    activity_type: str | None = None
    activity_name: str | None = None
    start_time: str | None = None
    summary: ActivitySummary | None = None
    weather: WeatherData | None = None
    hr_zones: list[HeartRateZone] | None = None
    laps: list[dict[str, Any]] | None = None  # Complex structure, keeping as Dict for now


@dataclass
class PhysiologicalMarkers:
    resting_heart_rate: int | None = None
    vo2_max: float | None = None
    hrv: dict[str, Any] | None = None  # Complex nested structure, keeping as Dict for now


@dataclass
class BodyMetrics:
    weight: dict[str, Any] | None = None  # Complex nested structure with historical data
    hydration: list[dict[str, Any]] | None = None  # Complex structure with daily data


@dataclass
class RecoveryIndicators:
    date: str | None = None
    sleep: dict[str, Any] | None = None  # Complex nested structure
    stress: dict[str, Any] | None = None  # Complex nested structure


@dataclass
class TrainingStatus:
    vo2_max: dict[str, Any] | None = None
    acute_training_load: dict[str, Any] | None = None


@dataclass
class GarminData:
    user_profile: UserProfile | None = None
    daily_stats: DailyStats | None = None
    recent_activities: list[Activity] | None = None
    all_activities: list[Activity] | None = None
    physiological_markers: PhysiologicalMarkers | None = None
    body_metrics: BodyMetrics | None = None
    recovery_indicators: list[RecoveryIndicators] | None = None
    training_status: TrainingStatus | None = None
    vo2_max_history: dict[str, list[dict[str, Any]]] | None = None
    training_load_history: list[dict[str, Any]] | None = None
