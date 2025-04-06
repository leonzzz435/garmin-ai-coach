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
    def extract_start_time(activity_data: Dict[str, Any]) -> Optional[str]:
        """Extract start time from activity data with fallbacks."""
        # Try different possible locations for start time
        start_time = None
        
        # Check in summaryDTO
        summary = activity_data.get('summaryDTO', {})
        if summary:
            start_time = summary.get('startTimeLocal') or summary.get('startTimeGMT')
        
        # If not found, check directly in the activity
        if not start_time:
            start_time = (
                activity_data.get('startTimeLocal') or
                activity_data.get('startTimeGMT') or
                activity_data.get('startTime')
            )
        
        # If still not found, check in beginTimestamp
        if not start_time:
            start_time = activity_data.get('beginTimestamp')
            if start_time and isinstance(start_time, (int, float)):
                # Convert timestamp to ISO format if it's a number
                from datetime import datetime
                start_time = datetime.fromtimestamp(start_time / 1000).isoformat()
        
        return start_time
    
    @staticmethod
    def extract_activity_type(activity_data: Dict[str, Any]) -> str:
        """Extract activity type from activity data with fallbacks."""
        # Try different possible locations for activity type
        activity_type = None
        
        # Check in activityType
        activity_type_data = activity_data.get('activityType', {})
        if activity_type_data:
            activity_type = activity_type_data.get('typeKey') or activity_type_data.get('type')
        
        # If not found, check in activityTypeDTO
        if not activity_type:
            activity_type_dto = activity_data.get('activityTypeDTO', {})
            if activity_type_dto:
                activity_type = activity_type_dto.get('typeKey') or activity_type_dto.get('type')
        
        # If still not found, check directly in the activity
        if not activity_type:
            activity_type = activity_data.get('activityType')
            if isinstance(activity_type, str):
                return activity_type
        
        return activity_type or 'unknown'

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
                
                # Add power data if available
                if 'averagePower' in lap:
                    processed_lap['averagePower'] = lap.get('averagePower')
                if 'maxPower' in lap:
                    processed_lap['maxPower'] = lap.get('maxPower')
                if 'minPower' in lap:
                    processed_lap['minPower'] = lap.get('minPower')
                if 'normalizedPower' in lap:
                    processed_lap['normalizedPower'] = lap.get('normalizedPower')
                if 'totalWork' in lap:
                    processed_lap['totalWork'] = lap.get('totalWork')
                
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

            # Try to get additional details for the multisport activity
            try:
                activity_details = self.garmin.client.get_activity_details(activity_id)
                if activity_details:
                    # Merge the details with the main activity data
                    for key, value in activity_details.items():
                        if key not in detailed_activity:
                            detailed_activity[key] = value
                    logger.info(f"Successfully fetched additional details for multisport activity {activity_id}")
            except Exception as e:
                logger.warning(f"Failed to get additional details for multisport activity {activity_id}: {e}")

            child_activities = []
            metadata = detailed_activity.get('metadataDTO', {})
            child_ids = metadata.get('childIds', [])
            child_types = metadata.get('childActivityTypes', [])

            if not child_ids or not child_types:
                logger.warning(f"Multisport activity {activity_id} missing child IDs in metadata")
                
                # Try alternative approach - some versions of the API might store this differently
                # Check if there's a childActivities field
                child_activities_data = detailed_activity.get('childActivities', [])
                if child_activities_data:
                    logger.info(f"Found {len(child_activities_data)} child activities in childActivities field")
                    child_ids = [child.get('activityId') for child in child_activities_data if child.get('activityId')]
                    
                    # Try to extract child types if available
                    if not child_types and child_ids:
                        child_types = [child.get('activityType', {}).get('typeKey', 'unknown')
                                      for child in child_activities_data if child.get('activityId')]
                
                # Try another alternative - check if there's a childIds field directly in the activity
                direct_child_ids = detailed_activity.get('childIds', [])
                if direct_child_ids and not child_ids:
                    logger.info(f"Found {len(direct_child_ids)} child IDs directly in activity")
                    child_ids = direct_child_ids
                
                if not child_ids:
                    logger.warning(f"Could not find any child activities for multisport activity {activity_id}")
                    return None

            # Process each child activity
            for i, child_id in enumerate(child_ids):
                try:
                    logger.info(f"Fetching child activity {child_id}")
                    child_activity = self.garmin.client.get_activity(child_id)
                    if not child_activity:
                        logger.warning(f"Failed to get child activity {child_id}")
                        continue

                    # Try to get additional details for the child activity
                    try:
                        child_activity_details = self.garmin.client.get_activity_details(child_id)
                        if child_activity_details:
                            # Merge the details with the main activity data
                            for key, value in child_activity_details.items():
                                if key not in child_activity:
                                    child_activity[key] = value
                            logger.info(f"Successfully fetched additional details for child activity {child_id}")
                    except Exception as e:
                        logger.warning(f"Failed to get additional details for child activity {child_id}: {e}")

                    # Get child activity type
                    child_type = None
                    if i < len(child_types):
                        child_type = child_types[i]
                    else:
                        # Extract from the activity data
                        child_type = self.extract_activity_type(child_activity)
                    
                    # Get child start time
                    child_start_time = self.extract_start_time(child_activity)
                    
                    # Extract summary from summaryDTO
                    child_summary = self._extract_activity_summary(child_activity.get('summaryDTO', {}))
                    
                    # For cycling segments, check if power data is at the top level
                    if child_type == 'cycling':
                        # Update power fields if they exist at the top level but not in summaryDTO
                        if child_summary.avg_power is None:
                            # Try different possible field names for average power
                            child_summary.avg_power = (
                                child_activity.get('avgPower') or
                                child_activity.get('averagePower')
                            )
                            
                        if child_summary.max_power is None:
                            child_summary.max_power = child_activity.get('maxPower')
                            
                        if child_summary.normalized_power is None:
                            # Try different possible field names for normalized power
                            child_summary.normalized_power = (
                                child_activity.get('normPower') or
                                child_activity.get('normalizedPower')
                            )
                            
                        if child_summary.training_stress_score is None:
                            child_summary.training_stress_score = child_activity.get('trainingStressScore')
                            
                        if child_summary.intensity_factor is None:
                            child_summary.intensity_factor = child_activity.get('intensityFactor')
                    
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
                        'activityId': child_id,
                        'activityName': child_activity.get('activityName'),
                        'activityType': child_type,
                        'startTime': child_start_time,
                        'summary': child_summary,
                        'hr_zones': self._extract_hr_zone_data(child_hr_zones),
                        'laps': child_lap_data
                    })
                    logger.info(f"Successfully processed child activity {child_id} of type {child_type}")
                except Exception as e:
                    logger.error(f"Error processing child activity {child_id}: {e}")
                    logger.debug(traceback.format_exc())
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
            
            # Extract start time with fallback logic
            start_time = self.extract_start_time(detailed_activity)
            
            logger.info(f"Processed multisport activity - Name: {activity_name}, Start Time: {start_time}")

            # Extract summary from summaryDTO
            summary = self._extract_activity_summary(detailed_activity.get('summaryDTO', {}))
            
            # For multi-sport activities with cycling segments, try to get power data from cycling segments
            cycling_segments = [child for child in child_activities if child.get('activityType') == 'cycling']
            if cycling_segments and (summary.avg_power is None or summary.max_power is None or summary.normalized_power is None):
                # Find the first cycling segment with power data
                for segment in cycling_segments:
                    segment_summary = segment.get('summary')
                    if segment_summary:
                        # Update power fields if they're missing in the main summary
                        if summary.avg_power is None and segment_summary.avg_power is not None:
                            summary.avg_power = segment_summary.avg_power
                        if summary.max_power is None and segment_summary.max_power is not None:
                            summary.max_power = segment_summary.max_power
                        if summary.normalized_power is None and segment_summary.normalized_power is not None:
                            summary.normalized_power = segment_summary.normalized_power
                        if summary.training_stress_score is None and segment_summary.training_stress_score is not None:
                            summary.training_stress_score = segment_summary.training_stress_score
                        if summary.intensity_factor is None and segment_summary.intensity_factor is not None:
                            summary.intensity_factor = segment_summary.intensity_factor
            
            return Activity(
                activity_id=activity_id,
                activity_type='multisport',
                activity_name=activity_name,
                start_time=start_time,
                summary=summary,
                weather=self._extract_weather_data(weather_data),
                hr_zones=[],  # Multisport activities don't have overall HR zones
                laps=child_activities  # Store child activities in the laps field for now
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
            
            # Try to get additional details for the activity
            try:
                activity_details = self.garmin.client.get_activity_details(activity_id)
                if activity_details:
                    # Merge the details with the main activity data
                    for key, value in activity_details.items():
                        if key not in detailed_activity:
                            detailed_activity[key] = value
                    logger.info(f"Successfully fetched additional details for activity {activity_id}")
            except Exception as e:
                logger.warning(f"Failed to get additional details for activity {activity_id}: {e}")
            
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
            
            # Extract activity type with helper function
            activity_type = self.extract_activity_type(detailed_activity)
            
            # Normalize swimming activities
            if activity_type in ['open_water_swimming', 'lap_swimming']:
                activity_type = 'swimming'
                
            # Extract activity name with more robust fallback logic
            activity_name = (
                detailed_activity.get('activityName') or
                detailed_activity.get('name') or
                f"{activity_type.replace('_', ' ').title()} Activity"
            )
            
            # Extract start time with helper function
            start_time = self.extract_start_time(detailed_activity)
            
            logger.info(f"Processed activity - Type: {activity_type}, Name: {activity_name}, Start Time: {start_time}")

            # Extract summary from summaryDTO
            summary = self._extract_activity_summary(detailed_activity.get('summaryDTO', {}))
            
            # For cycling activities, check if power data is at the top level
            if activity_type == 'cycling':
                # Update power fields if they exist at the top level but not in summaryDTO
                if summary.avg_power is None:
                    # Try different possible field names for average power
                    summary.avg_power = (
                        detailed_activity.get('avgPower') or
                        detailed_activity.get('averagePower')
                    )
                    
                if summary.max_power is None:
                    summary.max_power = detailed_activity.get('maxPower')
                    
                if summary.normalized_power is None:
                    # Try different possible field names for normalized power
                    summary.normalized_power = (
                        detailed_activity.get('normPower') or
                        detailed_activity.get('normalizedPower')
                    )
                    
                if summary.training_stress_score is None:
                    summary.training_stress_score = detailed_activity.get('trainingStressScore')
                    
                if summary.intensity_factor is None:
                    summary.intensity_factor = detailed_activity.get('intensityFactor')
                
                # If we still don't have power data, try to get it from the first lap
                if (summary.avg_power is None or summary.normalized_power is None) and lap_data:
                    first_lap = lap_data[0]
                    if summary.avg_power is None and 'averagePower' in first_lap:
                        summary.avg_power = first_lap['averagePower']
                    if summary.normalized_power is None and 'normalizedPower' in first_lap:
                        summary.normalized_power = first_lap['normalizedPower']
            
            return Activity(
                activity_id=activity_id,
                activity_type=activity_type,
                activity_name=activity_name,
                start_time=start_time,
                summary=summary,
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
        # For cycling activities, power data might be in the top-level activity object
        # We'll handle this in the _process_single_sport_activity method
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
            activity_training_load=summary.get('activityTrainingLoad'),
            moderate_intensity_minutes=summary.get('moderateIntensityMinutes'),
            vigorous_intensity_minutes=summary.get('vigorousIntensityMinutes'),
            recovery_heart_rate=summary.get('recoveryHeartRate'),
            # Power-related fields for cycling activities
            avg_power=summary.get('avgPower'),
            max_power=summary.get('maxPower'),
            normalized_power=summary.get('normPower'),
            training_stress_score=summary.get('trainingStressScore'),
            intensity_factor=summary.get('intensityFactor')
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
        try:
            logger.info(f"Fetching training status for date: {date_obj.isoformat()}")
            raw_data = self.garmin.client.get_training_status(date_obj.isoformat())
            
            if raw_data is None:
                logger.warning("Training status data is None")
                return TrainingStatus(
                    vo2_max={'value': None, 'date': None},
                    acute_training_load={'acute_load': None, 'chronic_load': None, 'acwr': None}
                )
            
            # Log the raw data structure to understand what we're getting
            logger.debug(f"Raw training status data: {raw_data}")
            
            # Check for mostRecentVO2Max
            most_recent_vo2max = raw_data.get('mostRecentVO2Max')
            if most_recent_vo2max is None:
                logger.warning("mostRecentVO2Max is None in training status data")
                vo2max_data = None
            else:
                # Check for generic data
                generic_data = most_recent_vo2max.get('generic')
                if generic_data is None:
                    logger.warning("generic data is None in mostRecentVO2Max")
                    vo2max_data = None
                else:
                    vo2max_data = generic_data
                    logger.info(f"Found VO2Max data: {vo2max_data}")
            
            status = raw_data.get('mostRecentTrainingStatus', {}).get('latestTrainingStatusData', {})
            status_key = next(iter(status), None)
            status_data = status.get(status_key, {}) if status_key else {}
            
            if status_key is None:
                logger.warning("No status key found in latestTrainingStatusData")
            else:
                logger.info(f"Found status key: {status_key}")
                
        except Exception as e:
            logger.error(f"Error getting training status: {str(e)}")
            return TrainingStatus(
                vo2_max={'value': None, 'date': None},
                acute_training_load={'acute_load': None, 'chronic_load': None, 'acwr': None}
            )

        # Handle the case where vo2max_data is None
        vo2max_value = None
        vo2max_date = None
        
        if vo2max_data is not None:
            vo2max_value = vo2max_data.get('vo2MaxValue')
            vo2max_date = vo2max_data.get('calendarDate')
            logger.info(f"VO2Max value: {vo2max_value}, date: {vo2max_date}")
        else:
            logger.warning("vo2max_data is None, cannot extract vo2MaxValue")

        return TrainingStatus(
            vo2_max={
                'value': vo2max_value,
                'date': vo2max_date,
            },
            acute_training_load={
                'acute_load': status_data.get('acuteTrainingLoadDTO', {}).get('dailyTrainingLoadAcute'),
                'chronic_load': status_data.get('acuteTrainingLoadDTO', {}).get('dailyTrainingLoadChronic'),
                'acwr': status_data.get('acuteTrainingLoadDTO', {}).get('dailyAcuteChronicWorkloadRatio'),
            }
        )

    def get_vo2_max_history(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Get VO2 Max history for the given date range."""
        history = []
        current_date = start_date
        logger.info(f"Fetching VO2 max history from {start_date} to {end_date}")
        
        while current_date <= end_date:
            try:
                logger.info(f"Fetching VO2 max data for date: {current_date.isoformat()}")
                data = self.garmin.client.get_training_status(current_date.isoformat())
                
                if data is None:
                    logger.warning(f"Training status data is None for date {current_date.isoformat()}, possibly no VO2 max data available for this user")
                    current_date += timedelta(days=1)
                    continue
                
                # Check for mostRecentVO2Max
                most_recent_vo2max = data.get('mostRecentVO2Max')
                if most_recent_vo2max is None:
                    logger.warning(f"mostRecentVO2Max is None for date {current_date.isoformat()}")
                    current_date += timedelta(days=1)
                    continue
                
                # Check for generic data
                generic_data = most_recent_vo2max.get('generic')
                if generic_data is None:
                    logger.warning(f"generic data is None in mostRecentVO2Max for date {current_date.isoformat()}")
                    current_date += timedelta(days=1)
                    continue
                
                vo2max_data = generic_data
                vo2max_value = vo2max_data.get('vo2MaxValue')
                calendar_date = vo2max_data.get('calendarDate')
                
                if vo2max_value is not None and calendar_date is not None:
                    logger.info(f"Found VO2Max data for date {current_date.isoformat()}: value={vo2max_value}, date={calendar_date}")
                    history.append({
                        'date': calendar_date,
                        'value': vo2max_value,
                    })
                else:
                    logger.warning(f"VO2Max data missing value or date for {current_date.isoformat()}")
            except Exception as e:
                logger.error(f"Error getting VO2 max history for date {current_date.isoformat()}: {str(e)}")
                logger.debug(traceback.format_exc())
            
            current_date += timedelta(days=1)
        
        logger.info(f"Collected {len(history)} VO2 max history entries")
        return history

    def get_training_load_history(self, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Get training load history for the given date range."""
        history = []
        current_date = start_date
        logger.info(f"Fetching training load history from {start_date} to {end_date}")
        
        while current_date <= end_date:
            try:
                logger.info(f"Fetching training load data for date: {current_date.isoformat()}")
                data = self.garmin.client.get_training_status(current_date.isoformat())
                
                if data is None:
                    logger.warning(f"Training status data is None for date {current_date.isoformat()}, possibly no training load data available for this user")
                    current_date += timedelta(days=1)
                    continue
                
                # Check for mostRecentTrainingStatus
                most_recent_status = data.get('mostRecentTrainingStatus')
                if most_recent_status is None:
                    logger.warning(f"mostRecentTrainingStatus is None for date {current_date.isoformat()}")
                    current_date += timedelta(days=1)
                    continue
                
                # Check for latestTrainingStatusData
                latest_status_data = most_recent_status.get('latestTrainingStatusData')
                if latest_status_data is None or not isinstance(latest_status_data, dict) or len(latest_status_data) == 0:
                    logger.warning(f"latestTrainingStatusData is None or empty for date {current_date.isoformat()}")
                    current_date += timedelta(days=1)
                    continue
                
                status = latest_status_data
                status_key = next(iter(status), None)
                
                if status_key is None:
                    logger.warning(f"No status key found in latestTrainingStatusData for date {current_date.isoformat()}")
                    current_date += timedelta(days=1)
                    continue
                
                status_data = status[status_key]
                
                # Check for acuteTrainingLoadDTO
                acute_training_load_dto = status_data.get('acuteTrainingLoadDTO')
                if acute_training_load_dto is None:
                    logger.warning(f"acuteTrainingLoadDTO is None for date {current_date.isoformat()}")
                    current_date += timedelta(days=1)
                    continue
                
                acute_load = acute_training_load_dto.get('dailyTrainingLoadAcute')
                chronic_load = acute_training_load_dto.get('dailyTrainingLoadChronic')
                acwr = acute_training_load_dto.get('dailyAcuteChronicWorkloadRatio')
                
                logger.info(f"Found training load data for date {current_date.isoformat()}: acute={acute_load}, chronic={chronic_load}, acwr={acwr}")
                
                history.append({
                    'date': current_date.isoformat(),
                    'acute_load': acute_load,
                    'chronic_load': chronic_load,
                    'acwr': acwr,
                })
            except Exception as e:
                logger.error(f"Error getting training load history for date {current_date.isoformat()}: {str(e)}")
                logger.debug(traceback.format_exc())
                
            current_date += timedelta(days=1)
        
        logger.info(f"Collected {len(history)} training load history entries")
        return history
