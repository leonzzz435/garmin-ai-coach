import logging
import traceback
from datetime import date, timedelta
from typing import Dict, Any, List, Optional

from .client import GarminConnectClient
from .models import (
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

logger = logging.getLogger(__name__)

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
    def convert_lactate_threshold_speed(speed_au: Optional[float]) -> Optional[float]:
        """Convert lactate threshold speed from AU to m/s.
        1 AU = 10 m/s
        Returns speed in meters per second
        """
        if speed_au is None:
            return None
        speed_ms = speed_au * 10  # Convert AU to m/s
        if speed_ms == 0:
            return None
        return round(speed_ms, 2)  # Return speed in m/s

    def get_latest_sleep_duration(self, date_obj: date) -> Optional[float]:
        """Get the most recent night's sleep duration from recovery indicators."""
        try:
            sleep_data = self.garmin.client.get_sleep_data(date_obj.isoformat())
            daily_sleep = sleep_data.get('dailySleepDTO', {})
            return self.safe_divide_and_round(daily_sleep.get('sleepTimeSeconds'), 3600)
        except Exception as e:
            logger.error(f"Error getting sleep duration: {str(e)}")
            return None

    @staticmethod
    def get_date_ranges(config: ExtractionConfig) -> Dict[str, Dict[str, date]]:
        """Calculate date ranges for different data types."""
        end_date = date.today()
        
        return {
            'activities': {
                'start': end_date - timedelta(days=config.activities_range),
                'end': end_date
            },
            'metrics': {
                'start': end_date - timedelta(days=config.metrics_range),
                'end': end_date
            }
        }

class TriathlonCoachDataExtractor(DataExtractor):
    """Extracts and processes triathlon-related data from Garmin Connect."""

    def __init__(self, email: str, password: str):
        """Initialize the Garmin client and login."""
        self.garmin = GarminConnectClient()
        self.garmin.connect(email, password)

    def extract_data(self, config: ExtractionConfig = ExtractionConfig()) -> GarminData:
        """Extract all relevant data based on configuration."""
        date_ranges = self.get_date_ranges(config)
        
        # Base data that's always included
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

        return GarminData(**data)

    def get_user_profile(self) -> UserProfile:
        """Get relevant user profile information."""
        full_profile = self.garmin.client.get_user_profile()
        user_data = full_profile.get('userData', {})
        sleep_data = full_profile.get('userSleep', {})
        
        # Convert lactate threshold speed from AU to m/s
        lt_speed_au = user_data.get('lactateThresholdSpeed')
        lt_speed_ms = self.convert_lactate_threshold_speed(lt_speed_au)
        
        return UserProfile(
            gender=user_data.get('gender'),
            weight=user_data.get('weight'),
            height=user_data.get('height'),
            birth_date=user_data.get('birthDate'),
            activity_level=user_data.get('activityLevel'),
            vo2max_running=user_data.get('vo2MaxRunning'),
            vo2max_cycling=user_data.get('vo2MaxCycling'),
            lactate_threshold_speed=lt_speed_ms,
            lactate_threshold_heart_rate=user_data.get('lactateThresholdHeartRate'),
            ftp_auto_detected=user_data.get('ftpAutoDetected'),
            available_training_days=user_data.get('availableTrainingDays'),
            preferred_long_training_days=user_data.get('preferredLongTrainingDays'),
            sleep_time=sleep_data.get('sleepTime'),
            wake_time=sleep_data.get('wakeTime')
        )

    def get_daily_stats(self, date_obj: date) -> DailyStats:
        """Get daily stats for the given date."""
        raw_data = self.garmin.client.get_stats(date_obj.isoformat())
        
        # Get sleep duration from recovery indicators for the night's sleep only
        sleep_hours = self.get_latest_sleep_duration(date_obj)
        sleep_seconds = int(sleep_hours * 3600) if sleep_hours is not None else None
        
        return DailyStats(
            date=raw_data.get('calendarDate'),
            total_steps=raw_data.get('totalSteps'),
            total_distance_meters=raw_data.get('totalDistanceMeters'),
            total_calories=raw_data.get('totalKilocalories'),
            active_calories=raw_data.get('activeKilocalories'),
            bmr_calories=raw_data.get('bmrKilocalories'),
            wellness_start_time=raw_data.get('wellnessStartTimeLocal'),
            wellness_end_time=raw_data.get('wellnessEndTimeLocal'),
            duration_in_hours=self.safe_divide_and_round(raw_data.get('durationInMilliseconds'), 3600000),
            min_heart_rate=raw_data.get('minHeartRate'),
            max_heart_rate=raw_data.get('maxHeartRate'),
            resting_heart_rate=raw_data.get('restingHeartRate'),
            average_stress_level=raw_data.get('averageStressLevel'),
            max_stress_level=raw_data.get('maxStressLevel'),
            stress_duration_seconds=raw_data.get('stressDuration'),
            sleeping_seconds=sleep_seconds,
            sleeping_hours=sleep_hours,
            body_battery_highest=raw_data.get('bodyBatteryHighestValue'),
            body_battery_lowest=raw_data.get('bodyBatteryLowestValue'),
            body_battery_most_recent=raw_data.get('bodyBatteryMostRecentValue'),
            respiration_average=raw_data.get('avgWakingRespirationValue'),
            respiration_highest=raw_data.get('highestRespirationValue'),
            respiration_lowest=raw_data.get('lowestRespirationValue')
        )

    def get_activity_laps(self, activity_id: int) -> List[Dict[str, Any]]:
        """Get detailed lap data for a specific activity."""
        try:
            lap_data = self.garmin.client.get_activity_splits(activity_id)['lapDTOs']
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
            logger.error(f"Error fetching lap data for activity {activity_id}: {str(e)}")
            return []

    def get_recent_activities(self, start_date: date, end_date: date) -> List[Activity]:
        """Get recent activities with focused, relevant information."""
        try:
            logger.info(f"Fetching activities between {start_date} and {end_date}")
            
            activities = self.garmin.client.get_activities_by_date(
                start_date.isoformat(), 
                end_date.isoformat()
            )
            
            # Log the raw activities data for debugging
            logger.debug(f"Raw activities data: {activities}")
            
            if not activities:
                logger.warning(f"No activities found between {start_date} and {end_date}")
                return []
                
            logger.info(f"Found {len(activities)} activities")
            
            focused_activities = []
            for activity in activities:
                try:
                    activity_id = activity.get('activityId')
                    if not activity_id:
                        logger.warning("Activity missing activityId, skipping")
                        continue
                        
                    logger.info(f"Fetching details for activity {activity_id}")
                    detailed_activity = self.garmin.client.get_activity(activity_id)
                    
                    if not detailed_activity:
                        logger.warning(f"No details found for activity {activity_id}, skipping")
                        continue

                    if detailed_activity.get('isMultiSportParent', False):
                        focused_activity = self._process_multisport_activity(detailed_activity)
                    else:
                        focused_activity = self._process_single_sport_activity(detailed_activity)

                    focused_activities.append(focused_activity)
                except Exception as e:
                    logger.error(f"Error processing activity {activity.get('activityId')}: {str(e)}")
                    logger.debug(traceback.format_exc())
                    continue

            # Filter out None values and ensure all activities are Activity objects
            valid_activities = []
            for a in focused_activities:
                if a is not None:
                    if isinstance(a, dict):
                        valid_activities.append(Activity(**a))
                    elif isinstance(a, Activity):
                        valid_activities.append(a)
                    
            logger.info(f"Successfully processed {len(valid_activities)} out of {len(activities)} activities")
            return valid_activities
        except Exception as e:
            logger.error(f"Error fetching activities: {str(e)}")
            logger.debug(traceback.format_exc())
            return []

    def _process_multisport_activity(self, detailed_activity: Dict[str, Any]) -> Optional[Activity]:
        """Process a multisport activity."""
        try:
            activity_id = detailed_activity.get('activityId')
            if not activity_id:
                logger.warning("Multisport activity missing activityId")
                return None

            logger.info(f"Processing multisport activity {activity_id}")
            
            try:
                weather_data = self.garmin.client.get_activity_weather(activity_id)
            except Exception as e:
                logger.warning(f"Failed to get weather data for multisport activity {activity_id}: {e}")
                weather_data = None

            child_activities = []
            metadata = detailed_activity.get('metadataDTO', {})
            child_ids = metadata.get('childIds', [])
            child_types = metadata.get('childActivityTypes', [])

            if not child_ids or not child_types:
                logger.warning(f"Multisport activity {activity_id} missing child activities")
                return None

            for child_id, child_type in zip(child_ids, child_types):
                try:
                    child_activity = self.garmin.client.get_activity(child_id)
                    if not child_activity:
                        logger.warning(f"Failed to get child activity {child_id}")
                        continue

                    child_summary = self._extract_activity_summary(child_activity.get('summaryDTO', {}))
                    
                    try:
                        child_hr_zones = self.garmin.client.get_activity_hr_in_timezones(child_id)
                    except Exception as e:
                        logger.warning(f"Failed to get HR zones for child activity {child_id}: {e}")
                        child_hr_zones = []
                        
                    try:
                        child_lap_data = self.get_activity_laps(child_id)
                    except Exception as e:
                        logger.warning(f"Failed to get lap data for child activity {child_id}: {e}")
                        child_lap_data = []

                    child_activities.append({
                        'activityType': child_type,
                        'summary': child_summary,
                        'hr_zones': self._extract_hr_zone_data(child_hr_zones),
                        'laps': child_lap_data
                    })
                except Exception as e:
                    logger.error(f"Error processing child activity {child_id}: {e}")
                    continue

            if not child_activities:
                logger.warning(f"No valid child activities found for multisport activity {activity_id}")
                return None

            # Extract activity name with fallback logic
            activity_name = (
                detailed_activity.get('activityName') or
                detailed_activity.get('name') or
                'Multisport Activity'
            )
            
            logger.info(f"Processed multisport activity - Name: {activity_name}")

            return Activity(
                activity_id=activity_id,
                activity_type='multisport',
                activity_name=activity_name,
                start_time=detailed_activity.get('summaryDTO', {}).get('startTimeLocal'),
                summary=self._extract_activity_summary(detailed_activity.get('summaryDTO', {})),
                weather=self._extract_weather_data(weather_data),
                hr_zones=[],  # Multisport activities don't have overall HR zones
                laps=[]  # Multisport activities don't have overall laps
            )
        except Exception as e:
            logger.error(f"Error processing multisport activity: {str(e)}")
            logger.debug(traceback.format_exc())
            return None

    def _process_single_sport_activity(self, detailed_activity: Dict[str, Any]) -> Activity:
        """Process a single sport activity."""
        try:
            activity_id = detailed_activity.get('activityId')
            if not activity_id:
                logger.warning("Activity missing activityId")
                return None

            logger.info(f"Processing single sport activity {activity_id}")
            
            try:
                weather_data = self.garmin.client.get_activity_weather(activity_id)
            except Exception as e:
                logger.warning(f"Failed to get weather data for activity {activity_id}: {e}")
                weather_data = None
                
            try:
                hr_zones_data = self.garmin.client.get_activity_hr_in_timezones(activity_id)
            except Exception as e:
                logger.warning(f"Failed to get HR zones for activity {activity_id}: {e}")
                hr_zones_data = []
                
            try:
                lap_data = self.get_activity_laps(activity_id)
            except Exception as e:
                logger.warning(f"Failed to get lap data for activity {activity_id}: {e}")
                lap_data = []

            # Log the activity data structure for debugging
            logger.debug(f"Detailed activity data: {detailed_activity}")
            
            # Extract activity type with more robust fallback logic
            activity_type_data = detailed_activity.get('activityType', detailed_activity.get('activityTypeDTO', {}))
            activity_type = (
                activity_type_data.get('typeKey') or 
                activity_type_data.get('type') or 
                'unknown'
            )
            
            # Normalize swimming activities
            if activity_type in ['open_water_swimming', 'lap_swimming']:
                activity_type = 'swimming'
                
            # Extract activity name with more robust fallback logic
            activity_name = (
                detailed_activity.get('activityName') or
                detailed_activity.get('name') or
                f"{activity_type.replace('_', ' ').title()} Activity"
            )
            
            logger.info(f"Processed activity - Type: {activity_type}, Name: {activity_name}")

            return Activity(
                activity_id=activity_id,
                activity_type=activity_type,
                activity_name=activity_name,
                start_time=detailed_activity.get('summaryDTO', {}).get('startTimeLocal'),
                summary=self._extract_activity_summary(detailed_activity.get('summaryDTO', {})),
                weather=self._extract_weather_data(weather_data),
                hr_zones=self._extract_hr_zone_data(hr_zones_data),
                laps=lap_data
            )
        except Exception as e:
            logger.error(f"Error processing single sport activity: {str(e)}")
            logger.debug(traceback.format_exc())
            return None

    def _extract_activity_summary(self, summary: Dict[str, Any]) -> ActivitySummary:
        """Extract relevant summary data."""
        return ActivitySummary(
            distance=summary.get('distance'),
            duration=summary.get('duration'),
            moving_duration=summary.get('movingDuration'),
            elevation_gain=summary.get('elevationGain'),
            elevation_loss=summary.get('elevationLoss'),
            average_speed=summary.get('averageSpeed'),
            max_speed=summary.get('maxSpeed'),
            calories=summary.get('calories'),
            average_hr=summary.get('averageHR'),
            max_hr=summary.get('maxHR'),
            training_effect=summary.get('trainingEffect'),
            anaerobic_training_effect=summary.get('anaerobicTrainingEffect'),
            training_effect_label=summary.get('trainingEffectLabel'),
            activity_training_load=summary.get('activityTrainingLoad'),
            moderate_intensity_minutes=summary.get('moderateIntensityMinutes'),
            vigorous_intensity_minutes=summary.get('vigorousIntensityMinutes'),
            recovery_heart_rate=summary.get('recoveryHeartRate'),
            begin_potential_stamina=summary.get('beginPotentialStamina'),
            end_potential_stamina=summary.get('endPotentialStamina'),
            min_available_stamina=summary.get('minAvailableStamina'),
            difference_body_battery=summary.get('differenceBodyBattery')
        )

    def _extract_weather_data(self, weather: Dict[str, Any]) -> WeatherData:
        """Extract relevant weather data."""
        if not isinstance(weather, dict):
            return WeatherData(None, None, None, None, None)

        weather_type_dto = weather.get('weatherTypeDTO')
        weather_type = weather_type_dto.get('desc') if isinstance(weather_type_dto, dict) else None

        return WeatherData(
            temp=weather.get('temp'),
            apparent_temp=weather.get('apparentTemp'),
            relative_humidity=weather.get('relativeHumidity'),
            wind_speed=weather.get('windSpeed'),
            weather_type=weather_type
        )

    def _extract_hr_zone_data(self, hr_zones: List[Dict[str, Any]]) -> List[HeartRateZone]:
        """Extract relevant heart rate zone data."""
        if not hr_zones or not isinstance(hr_zones, list):
            logger.warning("No heart rate zones data available or invalid format")
            return []
            
        processed_zones = []
        for zone in hr_zones:
            try:
                if not isinstance(zone, dict):
                    logger.warning(f"Invalid zone data format: {zone}")
                    continue
                    
                processed_zones.append(HeartRateZone(
                    zone_number=zone.get('zoneNumber'),
                    secs_in_zone=zone.get('secsInZone'),
                    zone_low_boundary=zone.get('zoneLowBoundary')
                ))
            except Exception as e:
                logger.error(f"Error processing heart rate zone: {str(e)}")
                continue
                
        return processed_zones

    # The following methods remain largely unchanged but would be updated
    # to use the new models. They are included in the original class but
    # omitted here for brevity. In a real implementation, they would be
    # properly typed and use the appropriate model classes.
    
    def get_physiological_markers(self, start_date: date, end_date: date) -> PhysiologicalMarkers:
        """Get relevant physiological markers."""

        # Get resting heart rate
        rhr_data = self.garmin.client.get_rhr_day(end_date.isoformat())
        rhr_value = rhr_data.get('allMetrics', {}).get('metricsMap', {}).get('WELLNESS_RESTING_HEART_RATE', [])
        resting_heart_rate = rhr_value[0].get('value') if rhr_value else None

        # Get VO2 Max
        user_summary = self.garmin.client.get_user_summary(end_date.isoformat())
        vo2_max = user_summary.get('vo2Max')

        # Get HRV data with error handling
        try:
            hrv_data = self.garmin.client.get_hrv_data(end_date.isoformat())
            if hrv_data is None:
                logger.warning("HRV data is None, using empty dict for hrvSummary")
                hrv_summary = {}
            else:
                hrv_summary = hrv_data.get('hrvSummary', {})
        except Exception as e:
            logger.error(f"Error fetching HRV data: {str(e)}")
            hrv_summary = {}
        hrv = {
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

        return PhysiologicalMarkers(
            resting_heart_rate=resting_heart_rate,
            vo2_max=vo2_max,
            hrv=hrv
        )

    def get_body_metrics(self, start_date: date, end_date: date) -> BodyMetrics:
        """Get relevant body metrics in a clean format."""
        weight_data = self.garmin.client.get_body_composition(start_date.isoformat(), end_date.isoformat())
        hydration_data = [
            self.garmin.client.get_hydration_data(date.isoformat()) 
            for date in (start_date + timedelta(n) for n in range((end_date - start_date).days + 1))
        ]
        
        # Process weight data
        processed_weight_data = []
        for entry in weight_data.get('dateWeightList', []):
            weight = entry.get('weight')
            processed_weight_data.append({
                'date': entry.get('calendarDate'),
                'weight': round(weight / 1000, 2) if weight is not None else None,  # Convert to kg
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

        return BodyMetrics(
            weight={
                'data': processed_weight_data,
                'average': average_weight
            },
            hydration=processed_hydration_data
        )

    def get_recovery_indicators(self, start_date: date, end_date: date) -> List[RecoveryIndicators]:
        """Get relevant recovery indicators including sleep and stress data."""
        processed_data = []
        current_date = start_date

        while current_date <= end_date:
            sleep_data = self.garmin.client.get_sleep_data(current_date.isoformat())
            stress_data = self.garmin.client.get_stress_data(current_date.isoformat())

            daily_sleep = sleep_data.get('dailySleepDTO', {})
            sleep_scores = daily_sleep.get('sleepScores', {})

            processed_data.append(RecoveryIndicators(
                date=current_date.isoformat(),
                sleep={
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
                stress={
                    'max_level': stress_data.get('maxStressLevel'),
                    'avg_level': stress_data.get('avgStressLevel')
                }
            ))
            current_date += timedelta(days=1)

        return processed_data

    def get_training_status(self, date_obj: date) -> TrainingStatus:
        """Get relevant training status information."""
        raw_data = self.garmin.client.get_training_status(date_obj.isoformat())

        vo2max_data = raw_data.get('mostRecentVO2Max', {}).get('generic', {})
        training_load_balance = raw_data.get('mostRecentTrainingLoadBalance', {}).get('metricsTrainingLoadBalanceDTOMap', {})
        training_status = raw_data.get('mostRecentTrainingStatus', {}).get('latestTrainingStatusData', {})

        # Get the first (and usually only) key from the dictionaries
        load_balance_key = next(iter(training_load_balance), None)
        status_key = next(iter(training_status), None)

        load_balance = training_load_balance.get(load_balance_key, {}) if load_balance_key else {}
        status = training_status.get(status_key, {}) if status_key else {}

        return TrainingStatus(
            vo2_max={
                'value': vo2max_data.get('vo2MaxValue') if vo2max_data else None,
                'date': vo2max_data.get('calendarDate') if vo2max_data else None,
            },
            training_load_balance={
                'aerobic_low': load_balance.get('monthlyLoadAerobicLow'),
                'aerobic_high': load_balance.get('monthlyLoadAerobicHigh'),
                'anaerobic': load_balance.get('monthlyLoadAnaerobic'),
                'feedback': load_balance.get('trainingBalanceFeedbackPhrase'),
            },
            training_status={
                'status': status.get('trainingStatus'),
                'load_level_trend': status.get('loadLevelTrend'),
                'fitness_trend': status.get('fitnessTrend'),
                'feedback': status.get('trainingStatusFeedbackPhrase'),
            },
            acute_training_load={
                'acute_load': status.get('acuteTrainingLoadDTO', {}).get('dailyTrainingLoadAcute'),
                'chronic_load': status.get('acuteTrainingLoadDTO', {}).get('dailyTrainingLoadChronic'),
                'acwr': status.get('acuteTrainingLoadDTO', {}).get('dailyAcuteChronicWorkloadRatio'),
                'acwr_status': status.get('acuteTrainingLoadDTO', {}).get('acwrStatus'),
                'acwr_feedback': status.get('acuteTrainingLoadDTO', {}).get('acwrStatusFeedback'),
            }
        )

    def get_training_readiness_history(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Get training readiness history for the given date range."""
        history = []
        current_date = start_date
        while current_date <= end_date:
            data = self.garmin.client.get_training_readiness(current_date.isoformat())
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

    def get_race_predictions_history(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Get race predictions history for the given date range."""
        raw_data = self.garmin.client.get_race_predictions(start_date.isoformat(), end_date.isoformat(), _type="daily")
        return [
            {
                'date': prediction.get('calendarDate'),
                '5k': self._format_time(prediction.get('time5K')),
                '10k': self._format_time(prediction.get('time10K')),
                'half_marathon': self._format_time(prediction.get('timeHalfMarathon')),
                'marathon': self._format_time(prediction.get('timeMarathon')),
            }
            for prediction in raw_data
        ]

    def get_hill_score_history(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Get hill score history for the given date range."""
        raw_data = self.garmin.client.get_hill_score(start_date.isoformat(), end_date.isoformat())
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

    def get_endurance_score(self, date_obj: date) -> Dict[str, Any]:
        """Get endurance score information for a specific date."""
        raw_data = self.garmin.client.get_endurance_score(date_obj.isoformat())
        if not raw_data:
            return {}

        contributors = raw_data.get('contributors', [])
        processed_contributors = self._map_endurance_score_contributors(contributors)

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

    def get_endurance_score_history(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Get endurance score history for the given date range."""
        history = []
        current_date = start_date
        while current_date <= end_date:
            score_data = self.get_endurance_score(current_date)
            if score_data:
                history.append(score_data)
            current_date += timedelta(days=1)
        return history

    def get_vo2_max_history(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Get VO2 Max history for the given date range."""
        history = []
        current_date = start_date
        while current_date <= end_date:
            data = self.garmin.client.get_training_status(current_date.isoformat())
            vo2max_data = data.get('mostRecentVO2Max', {}).get('generic', {})
            if vo2max_data:
                history.append({
                    'date': vo2max_data.get('calendarDate'),
                    'value': vo2max_data.get('vo2MaxValue'),
                })
            current_date += timedelta(days=1)
        return history

    def get_training_load_history(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Get training load history for the given date range."""
        history = []
        current_date = start_date
        while current_date <= end_date:
            data = self.garmin.client.get_training_status(current_date.isoformat())
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

    @staticmethod
    def _format_time(seconds: Optional[int]) -> str:
        """Format seconds into HH:MM:SS."""
        if not seconds:
            return "N/A"
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    @staticmethod
    def _map_endurance_score_contributors(contributors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Map endurance score contributors to their respective disciplines."""
        discipline_map = {0: 'running', 1: 'cycling', 6: 'swimming', 8: 'other'}
        return [
            {'discipline': discipline_map.get(c['group'], 'unknown'), 'contribution': c['contribution']}
            for c in contributors
        ]
