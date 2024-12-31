# triathlon_data_extractor.py

import logging
import traceback
from typing import Dict, Any, List, Optional
import datetime
from datetime import timedelta
import pandas as pd
from garminconnect import Garmin
from dataclasses import dataclass
from enum import Enum

from utils.report_utils import (
    summarize_activities,
    summarize_training_volume,
    summarize_training_intensity,
    summarize_recovery,
    summarize_training_load,
    summarize_vo2max_evolution,
    summarize_readiness_evolution,
    summarize_race_predictions_weekly,
    summarize_hill_score_weekly,
    summarize_endurance_score_weekly
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TimeRange(Enum):
    RECENT = 21  # 3 weeks
    EXTENDED = 56  # 8 weeks

@dataclass
class ExtractionConfig:
    activities_range: int = TimeRange.RECENT.value
    metrics_range: int = TimeRange.EXTENDED.value
    include_detailed_activities: bool = True
    include_metrics: bool = True

class DataExtractor:
    """Base class for data extraction operations"""
    
    @staticmethod
    def safe_divide_and_round(numerator: Optional[float], 
                            denominator: float, 
                            decimal_places: int = 2) -> Optional[float]:
        """Safely perform division and rounding."""
        if numerator is None:
            return None
        return round(numerator / denominator, decimal_places)

    @staticmethod
    def get_date_ranges(config: ExtractionConfig) -> Dict[str, Dict[str, datetime.date]]:
        """Calculate date ranges for different data types."""
        end_date = datetime.date.today()
        
        return {
            'activities': {
                'start': end_date - datetime.timedelta(days=config.activities_range),
                'end': end_date
            },
            'metrics': {
                'start': end_date - datetime.timedelta(days=config.metrics_range),
                'end': end_date
            }
        }

class TriathlonCoachDataExtractor(DataExtractor):
    def __init__(self, email: str, password: str):
        """Initialize the Garmin client and login."""
        self.client = Garmin(email, password)
        self.client.login()

    def extract_data(self, config: ExtractionConfig = ExtractionConfig()) -> Dict[str, Any]:
        """Extract all relevant data based on configuration."""
        date_ranges = self.get_date_ranges(config)
        
        data = {
            "user_profile": self.get_user_profile(),
            "daily_stats": self.get_daily_stats(date_ranges['metrics']['end'])
        }

        # Recent activities (3 weeks)
        if config.include_detailed_activities:
            data.update({
                "recent_activities": self.get_recent_activities(
                    date_ranges['activities']['start'],
                    date_ranges['activities']['end']
                )
            })

        # Extended metrics (8 weeks)
        if config.include_metrics:
            data.update({
                "all_activities": self.get_recent_activities(
                    date_ranges['metrics']['start'],
                    date_ranges['metrics']['end']
                ),
                "physiological_markers": self.get_physiological_markers(
                    date_ranges['metrics']['start'],
                    date_ranges['metrics']['end']
                ),
                "body_metrics": self.get_body_metrics(
                    date_ranges['metrics']['start'],
                    date_ranges['metrics']['end']
                ),
                "recovery_indicators": self.get_recovery_indicators(
                    date_ranges['metrics']['start'],
                    date_ranges['metrics']['end']
                ),
                "training_status": self.get_training_status(
                    date_ranges['metrics']['end']
                ),
                "training_readiness": self.get_training_readiness_history(
                    date_ranges['metrics']['start'],
                    date_ranges['metrics']['end']
                ),
                "race_predictions": self.get_race_predictions_history(
                    date_ranges['metrics']['start'],
                    date_ranges['metrics']['end']
                ),
                "hill_score": self.get_hill_score_history(
                    date_ranges['metrics']['start'],
                    date_ranges['metrics']['end']
                ),
                'endurance_score': self.get_endurance_score(
                    date_ranges['metrics']['end']
                ),
                'endurance_score_history': self.get_endurance_score_history(
                    date_ranges['metrics']['start'],
                    date_ranges['metrics']['end']
                ),
                "vo2_max_history": self.get_vo2_max_history(
                    date_ranges['metrics']['start'],
                    date_ranges['metrics']['end']
                ),
                "training_load_history": self.get_training_load_history(
                    date_ranges['metrics']['start'],
                    date_ranges['metrics']['end']
                )
            })

        return data
    
    def get_daily_stats(self, date: datetime.date) -> Dict[str, Any]:
        """Get daily stats for the given date."""
        raw_data = self.client.get_stats(date.isoformat())
        # Process the raw data to extract relevant fields
        daily_stats = {
            'date': raw_data.get('calendarDate'),
            'total_steps': raw_data.get('totalSteps'),
            'total_distance_meters': raw_data.get('totalDistanceMeters'),
            'total_calories': raw_data.get('totalKilocalories'),
            'active_calories': raw_data.get('activeKilocalories'),
            'bmr_calories': raw_data.get('bmrKilocalories'),
            'wellness_start_time': raw_data.get('wellnessStartTimeLocal'),
            'wellness_end_time': raw_data.get('wellnessEndTimeLocal'),
            'duration_in_hours': self.safe_divide_and_round(raw_data.get('durationInMilliseconds'), 3600000),
            'min_heart_rate': raw_data.get('minHeartRate'),
            'max_heart_rate': raw_data.get('maxHeartRate'),
            'resting_heart_rate': raw_data.get('restingHeartRate'),
            'average_stress_level': raw_data.get('averageStressLevel'),
            'max_stress_level': raw_data.get('maxStressLevel'),
            'stress_duration_seconds': raw_data.get('stressDuration'),
            'sleeping_seconds': raw_data.get('sleepingSeconds'),
            'sleeping_hours': self.safe_divide_and_round(raw_data.get('sleepingSeconds'), 3600),
            'body_battery_highest': raw_data.get('bodyBatteryHighestValue'),
            'body_battery_lowest': raw_data.get('bodyBatteryLowestValue'),
            'body_battery_most_recent': raw_data.get('bodyBatteryMostRecentValue'),
            'respiration_average': raw_data.get('avgWakingRespirationValue'),
            'respiration_highest': raw_data.get('highestRespirationValue'),
            'respiration_lowest': raw_data.get('lowestRespirationValue'),
        }
        return daily_stats
    
    def get_training_load_history(self, start_date: datetime.date, end_date: datetime.date) -> List[Dict[str, Any]]:
        """Get training load history for the given date range."""
        history = []
        current_date = start_date
        while current_date <= end_date:
            data = self.client.get_training_status(current_date.isoformat())
            status = data.get('mostRecentTrainingStatus', {}).get('latestTrainingStatusData', {})
            status_key = next(iter(status), None)
            if status_key:
                status_data = status[status_key]
                history.append({
                    'date': current_date.isoformat(),
                    'acute_load': status_data.get('acuteTrainingLoadDTO', {}).get('dailyTrainingLoadAcute'),
                    'chronic_load': status_data.get('acuteTrainingLoadDTO', {}).get('dailyTrainingLoadChronic'),
                    'acwr': status_data.get('acuteTrainingLoadDTO', {}).get('dailyAcuteChronicWorkloadRatio'),
                })
            current_date += timedelta(days=1)
        return history

    def get_user_profile(self) -> Dict[str, Any]:
        """Get relevant user profile information."""
        full_profile = self.client.get_user_profile()
        user_data = full_profile.get('userData', {})
        
        relevant_profile = {
            'gender': user_data.get('gender'),
            'weight': user_data.get('weight'),
            'height': user_data.get('height'),
            'birthDate': user_data.get('birthDate'),
            'activityLevel': user_data.get('activityLevel'),
            'vo2MaxRunning': user_data.get('vo2MaxRunning'),
            'vo2MaxCycling': user_data.get('vo2MaxCycling'),
            'lactateThresholdSpeed': user_data.get('lactateThresholdSpeed'),
            'lactateThresholdHeartRate': user_data.get('lactateThresholdHeartRate'),
            'ftpAutoDetected': user_data.get('ftpAutoDetected'),
            'availableTrainingDays': user_data.get('availableTrainingDays'),
            'preferredLongTrainingDays': user_data.get('preferredLongTrainingDays'),
        }
        
        sleep_data = full_profile.get('userSleep', {})
        relevant_profile['sleepTime'] = sleep_data.get('sleepTime')
        relevant_profile['wakeTime'] = sleep_data.get('wakeTime')
        
        return relevant_profile

    def get_activity_laps(self, activity_id: int) -> List[Dict[str, Any]]:
        """Get detailed lap data for a specific activity."""
        try:
            lap_data = self.client.get_activity_splits(activity_id)['lapDTOs']
            processed_laps = []
            for lap in lap_data:
                processed_lap = {
                    'startTime': lap.get('startTimeGMT'),
                    'distance': round(lap.get('distance', 0) / 1000, 2),  # Convert to km
                    'duration': round(lap.get('duration', 0) / 60, 2),  # Convert to minutes
                    'elevationGain': lap.get('elevationGain'),
                    'elevationLoss': lap.get('elevationLoss'),
                    'averageSpeed': round(lap.get('averageSpeed', 0) * 3.6, 2),  # Convert to km/h
                    'maxSpeed': round(lap.get('maxSpeed', 0) * 3.6, 2),  # Convert to km/h
                    'averageHR': lap.get('averageHR'),
                    'maxHR': lap.get('maxHR'),
                    'calories': lap.get('calories'),
                    'intensity': lap.get('intensityType')
                }
                processed_laps.append(processed_lap)
            return processed_laps
        except Exception as e:
            print(f"Error fetching lap data for activity {activity_id}: {str(e)}")
            return []

    def get_recent_activities(self, start_date: datetime.date, end_date: datetime.date) -> List[Dict[str, Any]]:
        """Get recent activities with focused, relevant information."""
        activities = self.client.get_activities_by_date(start_date.isoformat(), end_date.isoformat())

        focused_activities = []
        for activity in activities:
            try:
                activity_id = activity['activityId']
                detailed_activity = self.client.get_activity(activity_id)

                if detailed_activity.get('isMultiSportParent', False):
                    # Handle multisport activity
                    focused_activity = self.process_multisport_activity(detailed_activity)
                else:
                    # Handle single sport activity
                    focused_activity = self.process_single_sport_activity(detailed_activity)

                focused_activities.append(focused_activity)
            except Exception as e:
                error_activity = {
                    'activityId': activity.get('activityId'),
                    'error': {
                        'type': type(e).__name__,
                        'message': str(e),
                        'traceback': traceback.format_exc()
                    }
                }
                focused_activities.append(error_activity)

        return focused_activities
    
    def process_multisport_activity(self, detailed_activity: Dict[str, Any]) -> Dict[str, Any]:
        """Process a multisport activity."""
        activity_id = detailed_activity['activityId']
        weather_data = self.client.get_activity_weather(activity_id)

        child_activities = []
        for child_id, child_type in zip(detailed_activity['metadataDTO']['childIds'], 
                                        detailed_activity['metadataDTO']['childActivityTypes']):
            child_activity = self.client.get_activity(child_id)
            child_summary = self.extract_summary_data(child_activity.get('summaryDTO', {}))
            child_hr_zones = self.client.get_activity_hr_in_timezones(child_id)
            child_lap_data = self.get_activity_laps(child_id)

            child_activities.append({
                'activityType': child_type,
                'summary': child_summary,
                'hr_zones': self.extract_hr_zone_data(child_hr_zones),
                'laps': child_lap_data
            })

        return {
            'activityId': activity_id,
            'activityType': 'multisport',
            'activityName': detailed_activity.get('activityName'),
            'startTime': detailed_activity.get('summaryDTO', {}).get('startTimeLocal'),
            'summary': self.extract_summary_data(detailed_activity.get('summaryDTO', {})),
            'weather': self.extract_weather_data(weather_data),
            'childActivities': child_activities,
            'childActivityTypes': detailed_activity['metadataDTO']['childActivityTypes']
        }
    
    def process_single_sport_activity(self, detailed_activity: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single sport activity."""
        activity_id = detailed_activity['activityId']
        weather_data = self.client.get_activity_weather(activity_id)
        hr_zones_data = self.client.get_activity_hr_in_timezones(activity_id)
        lap_data = self.get_activity_laps(activity_id)

        activity_type = detailed_activity.get('activityTypeDTO', {}).get('typeKey')
        if activity_type in ['open_water_swimming', 'lap_swimming']:
            activity_type = 'swimming'

        return {
            'activityId': activity_id,
            'activityType': activity_type,
            'activityName': detailed_activity.get('activityName'),
            'startTime': detailed_activity.get('summaryDTO', {}).get('startTimeLocal'),
            'summary': self.extract_summary_data(detailed_activity.get('summaryDTO', {})),
            'laps': lap_data,
            'weather': self.extract_weather_data(weather_data),
            'hr_zones': self.extract_hr_zone_data(hr_zones_data)
        }
    
    def extract_summary_data(self, summary: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant summary data."""
        return {
            'distance': summary.get('distance'),
            'duration': summary.get('duration'),
            'movingDuration': summary.get('movingDuration'),
            'elevationGain': summary.get('elevationGain'),
            'elevationLoss': summary.get('elevationLoss'),
            'averageSpeed': summary.get('averageSpeed'),
            'maxSpeed': summary.get('maxSpeed'),
            'calories': summary.get('calories'),
            'averageHR': summary.get('averageHR'),
            'maxHR': summary.get('maxHR'),
            'trainingEffect': summary.get('trainingEffect'),
            'anaerobicTrainingEffect': summary.get('anaerobicTrainingEffect'),
            'trainingEffectLabel': summary.get('trainingEffectLabel'),
            'activityTrainingLoad': summary.get('activityTrainingLoad'),
            'moderateIntensityMinutes': summary.get('moderateIntensityMinutes'),
            'vigorousIntensityMinutes': summary.get('vigorousIntensityMinutes'),
            'recoveryHeartRate': summary.get('recoveryHeartRate'),
            'beginPotentialStamina': summary.get('beginPotentialStamina'),
            'endPotentialStamina': summary.get('endPotentialStamina'),
            'minAvailableStamina': summary.get('minAvailableStamina'),
            'differenceBodyBattery': summary.get('differenceBodyBattery')
        }
    
    def extract_split_data(self, splits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract relevant split data."""
        focused_splits = []
        for split in splits:
            focused_split = {
                'distance': split.get('distance'),
                'duration': split.get('duration'),
                'movingDuration': split.get('movingDuration'),
                'elevationGain': split.get('elevationGain'),
                'averageSpeed': split.get('averageSpeed'),
                'maxSpeed': split.get('maxSpeed'),
                'calories': split.get('calories'),
                'averageHR': split.get('averageHR'),
                'maxHR': split.get('maxHR'),
                'splitType': split.get('splitType')
            }
            focused_splits.append(focused_split)
        return focused_splits

    def extract_weather_data(self, weather: Dict[str, Any]) -> Dict[str, Any]:
        """Extract relevant weather data."""
        if not isinstance(weather, dict):
            return {
                'temp': None,
                'apparentTemp': None,
                'relativeHumidity': None,
                'windSpeed': None,
                'weatherType': None
            }

        weather_type_dto = weather.get('weatherTypeDTO')
        weather_type = weather_type_dto.get('desc') if isinstance(weather_type_dto, dict) else None

        return {
            'temp': weather.get('temp'),
            'apparentTemp': weather.get('apparentTemp'),
            'relativeHumidity': weather.get('relativeHumidity'),
            'windSpeed': weather.get('windSpeed'),
            'weatherType': weather_type
        }

    def extract_hr_zone_data(self, hr_zones: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract relevant heart rate zone data."""
        return [
            {
                'zoneNumber': zone.get('zoneNumber'),
                'secsInZone': zone.get('secsInZone'),
                'zoneLowBoundary': zone.get('zoneLowBoundary')
            }
            for zone in hr_zones
        ]

    def get_physiological_markers(self, start_date: datetime.date, end_date: datetime.date) -> Dict[str, Any]:
        """Get relevant physiological markers."""
        data = {}

        # Get resting heart rate
        rhr_data = self.client.get_rhr_day(end_date.isoformat())
        rhr_value = rhr_data.get('allMetrics', {}).get('metricsMap', {}).get('WELLNESS_RESTING_HEART_RATE', [])
        if rhr_value:
            data['resting_heart_rate'] = rhr_value[0].get('value')
        else:
            data['resting_heart_rate'] = None

        # Get VO2 Max (assuming it's part of the user stats)
        user_summary = self.client.get_user_summary(end_date.isoformat())
        data['vo2_max'] = user_summary.get('vo2Max')

        # Get HRV data
        hrv_data = self.client.get_hrv_data(end_date.isoformat())
        hrv_summary = hrv_data.get('hrvSummary', {})
        data['hrv'] = {
            'weekly_avg': hrv_summary.get('weeklyAvg'),
            'last_night_avg': hrv_summary.get('lastNightAvg'),
            'last_night_5min_high': hrv_summary.get('lastNight5MinHigh'),
            'status': hrv_summary.get('status'),
            'baseline': {
                'low_upper': hrv_summary.get('baseline', {}).get('lowUpper'),
                'balanced_low': hrv_summary.get('baseline', {}).get('balancedLow'),
                'balanced_upper': hrv_summary.get('baseline', {}).get('balancedUpper'),
            }
        }
    
        return data

    def get_body_metrics(self, start_date: datetime.date, end_date: datetime.date) -> Dict[str, Any]:
        """Get relevant body metrics in a clean format."""
        weight_data = self.client.get_body_composition(start_date.isoformat(), end_date.isoformat())
        hydration_data = [self.client.get_hydration_data(date.isoformat()) for date in (start_date + datetime.timedelta(n) for n in range((end_date - start_date).days + 1))]
        
        # Process weight data
        processed_weight_data = []
        for entry in weight_data.get('dateWeightList', []):
            weight = entry.get('weight')
            processed_weight_data.append({
                'date': entry.get('calendarDate'),
                'weight': round(weight / 1000, 2) if weight is not None else None,  # Convert to kg and round to 2 decimal places
                'source': entry.get('sourceType')
            })

        # Calculate average weight
        total_average = weight_data.get('totalAverage', {})
        avg_weight = total_average.get('weight') if isinstance(total_average, dict) else None
        average_weight = round(avg_weight / 1000, 2) if avg_weight is not None else 0

        # Process hydration data
        processed_hydration_data = []
        for entry in hydration_data:
            goal_ml = entry.get('goalInML')
            value_ml = entry.get('valueInML')
            sweat_loss_ml = entry.get('sweatLossInML')
            
            processed_hydration_data.append({
                'date': entry.get('calendarDate'),
                'goal': round(goal_ml / 1000, 2) if goal_ml is not None else None,  # Convert to liters
                'intake': round(value_ml / 1000, 2) if value_ml is not None else None,  # Convert to liters
                'sweat_loss': round(sweat_loss_ml / 1000, 2) if sweat_loss_ml is not None else None  # Convert to liters
            })

        return {
            'weight': {
                'data': processed_weight_data,
                'average': average_weight
            },
            'hydration': processed_hydration_data
        }

    def get_recovery_indicators(self, start_date: datetime.date, end_date: datetime.date) -> Dict[str, Any]:
        """Get relevant recovery indicators including sleep and stress data."""
        processed_data = []

        current_date = start_date
        while current_date <= end_date:
            sleep_data = self.client.get_sleep_data(current_date.isoformat())
            stress_data = self.client.get_stress_data(current_date.isoformat())

            daily_sleep = sleep_data.get('dailySleepDTO', {})
            sleep_scores = daily_sleep.get('sleepScores', {})

            processed_entry = {
                'date': current_date.isoformat(),
                'sleep': {
                    'duration': {
                        'total': self.safe_divide_and_round(daily_sleep.get('sleepTimeSeconds'), 3600),
                        'deep': self.safe_divide_and_round(daily_sleep.get('deepSleepSeconds'), 3600),
                        'light': self.safe_divide_and_round(daily_sleep.get('lightSleepSeconds'), 3600),
                        'rem': self.safe_divide_and_round(daily_sleep.get('remSleepSeconds'), 3600),
                        'awake': self.safe_divide_and_round(daily_sleep.get('awakeSleepSeconds'), 3600)
                    },
                    'quality': {
                        'overall_score': sleep_scores.get('overall', {}).get('value'),
                        'deep_sleep': sleep_scores.get('deepPercentage', {}).get('value'),
                        'rem_sleep': sleep_scores.get('remPercentage', {}).get('value'),
                    },
                    'restless_moments': sleep_data.get('restlessMomentsCount'),
                    'avg_overnight_hrv': sleep_data.get('avgOvernightHrv'),
                    'hrv_status': sleep_data.get('hrvStatus'),
                    'body_battery_change': sleep_data.get('bodyBatteryChange'),
                    'resting_heart_rate': sleep_data.get('restingHeartRate')
                },
                'stress': {
                    'max_level': stress_data.get('maxStressLevel'),
                    'avg_level': stress_data.get('avgStressLevel')
                }
            }

            processed_data.append(processed_entry)
            current_date += datetime.timedelta(days=1)

        return processed_data

    def get_training_readiness(self, date: datetime.date) -> List[Dict[str, Any]]:
        """Get training readiness information."""
        raw_data = self.client.get_training_readiness(date.isoformat())
        if not raw_data:
            return []

        return [
            {
                'date': item.get('calendarDate'),
                'score': item.get('score'),
                'level': item.get('level'),
                'feedback': item.get('feedbackLong'),
                'sleep_score': item.get('sleepScore'),
                'recovery_time': item.get('recoveryTime'),
                'acute_load': item.get('acuteLoad'),
                'hrv_status': item.get('hrvFactorFeedback'),
            }
            for item in raw_data
        ]

    def get_race_predictions(self, start_date: datetime.date, end_date: datetime.date) -> List[Dict[str, Any]]:
        """Get race predictions for the given date range."""
        raw_data = self.client.get_race_predictions(start_date.isoformat(), end_date.isoformat(), _type="daily")
        
        return [
            {
                'date': prediction.get('calendarDate'),
                '5k': self.format_time(prediction.get('time5K')),
                '10k': self.format_time(prediction.get('time10K')),
                'half_marathon': self.format_time(prediction.get('timeHalfMarathon')),
                'marathon': self.format_time(prediction.get('timeMarathon')),
            }
            for prediction in raw_data
        ]

    def get_hill_score(self, start_date: datetime.date, end_date: datetime.date) -> List[Dict[str, Any]]:
        """Get hill score information for the given date range."""
        raw_data = self.client.get_hill_score(start_date.isoformat(), end_date.isoformat())
        
        if not raw_data or 'hillScoreDTOList' not in raw_data:
            return []

        return [
            {
                'date': score.get('calendarDate'),
                'overall_score': score.get('overallScore'),
                'strength_score': score.get('strengthScore'),
                'endurance_score': score.get('enduranceScore'),
                'classification': score.get('hillScoreClassificationId'),
            }
            for score in raw_data['hillScoreDTOList']
        ]

    def get_endurance_score(self, date: datetime.date) -> Dict[str, Any]:
        """Get endurance score information for a specific date."""
        raw_data = self.client.get_endurance_score(date.isoformat())
        
        if not raw_data:
            return {}

        contributors = raw_data.get('contributors', [])
        processed_contributors = self.map_endurance_score_contributors(contributors)

        return {
            'date': raw_data.get('calendarDate'),
            'overall_score': raw_data.get('overallScore'),
            'classification': raw_data.get('classification'),
            'feedback': raw_data.get('feedbackPhrase'),
            'contributors': processed_contributors,
            'gauge_lower_limit': raw_data.get('gaugeLowerLimit'),
            'gauge_upper_limit': raw_data.get('gaugeUpperLimit'),
            'classification_limits': {
                'intermediate': raw_data.get('classificationLowerLimitIntermediate'),
                'trained': raw_data.get('classificationLowerLimitTrained'),
                'well_trained': raw_data.get('classificationLowerLimitWellTrained'),
                'expert': raw_data.get('classificationLowerLimitExpert'),
                'superior': raw_data.get('classificationLowerLimitSuperior'),
                'elite': raw_data.get('classificationLowerLimitElite'),
            }
        }
    
    def get_training_readiness_history(self, start_date: datetime.date, end_date: datetime.date) -> List[Dict[str, Any]]:
        """Get training readiness history for the given date range."""
        history = []
        current_date = start_date
        while current_date <= end_date:
            data = self.client.get_training_readiness(current_date.isoformat())
            if data and len(data) > 0:
                latest_data = data[0]
                history.append({
                    'date': latest_data.get('calendarDate'),
                    'score': latest_data.get('score'),
                    'level': latest_data.get('level'),
                    'feedback': latest_data.get('feedbackLong'),
                    'sleep_score': latest_data.get('sleepScore'),
                    'recovery_time': latest_data.get('recoveryTime'),
                    'acute_load': latest_data.get('acuteLoad'),
                    'hrv_status': latest_data.get('hrvFactorFeedback'),
                })
            current_date += timedelta(days=1)
        return history
    
    def get_race_predictions_history(self, start_date: datetime.date, end_date: datetime.date) -> List[Dict[str, Any]]:
        """Get race predictions history for the given date range."""
        raw_data = self.client.get_race_predictions(start_date.isoformat(), end_date.isoformat(), _type="daily")
        return [
            {
                'date': prediction.get('calendarDate'),
                '5k': self.format_time(prediction.get('time5K')),
                '10k': self.format_time(prediction.get('time10K')),
                'half_marathon': self.format_time(prediction.get('timeHalfMarathon')),
                'marathon': self.format_time(prediction.get('timeMarathon')),
            }
            for prediction in raw_data
        ]
    
    def get_hill_score_history(self, start_date: datetime.date, end_date: datetime.date) -> List[Dict[str, Any]]:
        """Get hill score history for the given date range."""
        raw_data = self.client.get_hill_score(start_date.isoformat(), end_date.isoformat())
        if not raw_data or 'hillScoreDTOList' not in raw_data:
            return []
        return [
            {
                'date': score.get('calendarDate'),
                'overall_score': score.get('overallScore'),
                'strength_score': score.get('strengthScore'),
                'endurance_score': score.get('enduranceScore'),
                'classification': score.get('hillScoreClassificationId'),
            }
            for score in raw_data['hillScoreDTOList']
        ]
    
    def get_endurance_score_history(self, start_date: datetime.date, end_date: datetime.date) -> List[Dict[str, Any]]:
        """Get endurance score history for the given date range."""
        history = []
        current_date = start_date
        while current_date <= end_date:
            score_data = self.get_endurance_score(current_date)
            if score_data:
                history.append(score_data)
            current_date += timedelta(days=1)
        return history

    def get_training_status(self, date: datetime.date) -> Dict[str, Any]:
        """Get relevant training status information."""
        raw_data = self.client.get_training_status(date.isoformat())

        vo2max_data = raw_data.get('mostRecentVO2Max', {}).get('generic', {})
        training_load_balance = raw_data.get('mostRecentTrainingLoadBalance', {}).get('metricsTrainingLoadBalanceDTOMap', {})
        training_status = raw_data.get('mostRecentTrainingStatus', {}).get('latestTrainingStatusData', {})

        # Get the first (and usually only) key from the dictionaries
        load_balance_key = next(iter(training_load_balance), None)
        status_key = next(iter(training_status), None)

        load_balance = training_load_balance.get(load_balance_key, {}) if load_balance_key else {}
        status = training_status.get(status_key, {}) if status_key else {}

        relevant_data = {
            'vo2_max': {
                'value': vo2max_data.get('vo2MaxValue') if vo2max_data else None,
                'date': vo2max_data.get('calendarDate') if vo2max_data else None,
            },
            'training_load_balance': {
                'aerobic_low': load_balance.get('monthlyLoadAerobicLow'),
                'aerobic_high': load_balance.get('monthlyLoadAerobicHigh'),
                'anaerobic': load_balance.get('monthlyLoadAnaerobic'),
                'feedback': load_balance.get('trainingBalanceFeedbackPhrase'),
            },
            'training_status': {
                'status': status.get('trainingStatus'),
                'load_level_trend': status.get('loadLevelTrend'),
                'fitness_trend': status.get('fitnessTrend'),
                'feedback': status.get('trainingStatusFeedbackPhrase'),
            },
            'acute_training_load': {
                'acute_load': status.get('acuteTrainingLoadDTO', {}).get('dailyTrainingLoadAcute'),
                'chronic_load': status.get('acuteTrainingLoadDTO', {}).get('dailyTrainingLoadChronic'),
                'acwr': status.get('acuteTrainingLoadDTO', {}).get('dailyAcuteChronicWorkloadRatio'),
                'acwr_status': status.get('acuteTrainingLoadDTO', {}).get('acwrStatus'),
                'acwr_feedback': status.get('acuteTrainingLoadDTO', {}).get('acwrStatusFeedback'),
            },
        }

        return relevant_data
    
    @staticmethod
    def map_endurance_score_contributors(contributors):
        discipline_map = {0: 'running', 1: 'cycling', 6: 'swimming', 8: 'other'}
        return [
            {'discipline': discipline_map.get(c['group'], 'unknown'), 'contribution': c['contribution']}
            for c in contributors
        ]

    def get_vo2_max_history(self, start_date: datetime.date, end_date: datetime.date) -> List[Dict[str, Any]]:
        """Get VO2 Max history for the given date range."""
        history = []
        current_date = start_date
        while current_date <= end_date:
            data = self.client.get_training_status(current_date.isoformat())
            vo2max_data = data.get('mostRecentVO2Max', {}).get('generic', {})
            if vo2max_data:
                history.append({
                    'date': vo2max_data.get('calendarDate'),
                    'value': vo2max_data.get('vo2MaxValue'),
                })
            current_date += timedelta(days=1)
        return history

    @staticmethod
    def format_time(seconds: int) -> str:
        """Format seconds into HH:MM:SS."""
        if not seconds:
            return "N/A"
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
class ReportGenerator:
    """Handles the generation of reports from extracted data."""
    
    def __init__(self, data: Dict[str, Any]):
        self.data = data
        logger = logging.getLogger(__name__)
        logger.info(f"Initializing ReportGenerator with data keys: {list(data.keys())}")

    def generate_activities_report(self) -> str:
        """Generate activities-focused report."""
        logger = logging.getLogger(__name__)
        logger.info("Starting activities report generation")
        
        try:
            sections = [
                self._generate_user_profile_section(),
                self._generate_recent_activities_section(),
            ]
            logger.info("Successfully generated all report sections")
        except Exception as e:
            logger.error(f"Error generating report sections: {str(e)}", exc_info=True)
            raise
        
        return "\n\n".join(sections)

    def generate_metrics_report(self) -> str:
        """Generate metrics and analysis report."""
        sections = [
            self._generate_metrics_section(),
            self._generate_training_status_section(),
            self._generate_predictions_section()
        ]
        
        return "\n\n".join(sections)

    def generate_full_report(self) -> str:
        """Generate a complete markdown report."""
        sections = [
            self._generate_user_profile_section(),
            self._generate_recent_activities_section(),
            self._generate_metrics_section(),
            self._generate_training_status_section(),
            self._generate_predictions_section()
        ]
        
        return "\n\n".join(sections)

    def _generate_user_profile_section(self) -> str:
        """Generate the user profile section of the report."""
        profile = self.data['user_profile']
        
        weight = profile.get('weight')
        weight_kg = f"{weight / 1000:.2f} kg" if weight is not None else "N/A"
        
        return f"""# Athlete Profile
- **Gender**: {profile.get('gender')}
- **Weight**: {weight_kg}
- **Height**: {profile.get('height')} cm
- **Birth Date**: {profile.get('birthDate')}
- **Activity Level**: {profile.get('activityLevel')}
- **VO2Max (Running)**: {profile.get('vo2MaxRunning')} ml/kg/min
- **VO2Max (Cycling)**: {profile.get('vo2MaxCycling')} ml/kg/min
"""

    def _generate_recent_activities_section(self) -> str:
        """Generate the recent activities section of the report."""
        logger = logging.getLogger(__name__)
        try:
            if 'recent_activities' not in self.data:
                logger.error("No recent_activities found in data")
                return "No recent activities data available."
            
            activities = self.data['recent_activities']
            if not activities:
                logger.info("Empty recent_activities list")
                return "No activities found for the specified period."
            
            logger.info(f"Processing {len(activities)} activities")
            for idx, activity in enumerate(activities):
                logger.info(f"Activity {idx + 1} keys: {list(activity.keys())}")
            
            return summarize_activities(activities)
        except Exception as e:
            logger.error(f"Error in _generate_recent_activities_section: {str(e)}", exc_info=True)
            raise

    def _generate_metrics_section(self) -> str:
        """Generate the metrics section of the report."""
        return f"""# Performance Metrics

{summarize_training_volume(self.data['all_activities'])}

## Training Intensity
{summarize_training_intensity(self.data['all_activities'])}

## Recovery Metrics
{summarize_recovery(self.data['recovery_indicators'])}
"""

    def _generate_training_status_section(self) -> str:
        """Generate the training status section of the report."""
        return f"""# Training Status

## Load Evolution
{summarize_training_load(self.data['training_load_history'])}

## VO2Max Evolution
{summarize_vo2max_evolution(self.data['vo2_max_history'])}

{summarize_readiness_evolution(self.data['training_readiness'])}
"""

    def _generate_predictions_section(self) -> str:
        """Generate the predictions and scores section of the report."""
        return f"""# Performance Predictions and Scores

## Race Predictions Evolution
{summarize_race_predictions_weekly(self.data['race_predictions'])}

## Hill Score Evolution
{summarize_hill_score_weekly(self.data['hill_score'])}

## Endurance Score Evolution
{summarize_endurance_score_weekly(self.data['endurance_score_history'])}
"""
