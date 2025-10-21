# data_extractor.py
import logging
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from typing import Any

from .client import GarminConnectClient
from .models import (
    Activity,
    ActivitySummary,
    BodyMetrics,
    DailyStats,
    ExtractionConfig,
    GarminData,
    HeartRateZone,
    PhysiologicalMarkers,
    RecoveryIndicators,
    TrainingStatus,
    UserProfile,
    WeatherData,
)

logger = logging.getLogger(__name__)


def _to_float(v: Any) -> float | None:
    try:
        if v is None:
            return None
        if isinstance(v, bool):
            return None
        return float(v)
    except Exception:
        return None


def _to_int(v: Any) -> int | None:
    try:
        if v is None:
            return None
        if isinstance(v, bool):
            return None
        return int(v)
    except Exception:
        return None


def _round(v: Any, ndigits: int = 2) -> float | None:
    f = _to_float(v)
    return round(f, ndigits) if f is not None else None


def _dg(d: dict | None, key: str, default: Any = None) -> Any:
    """Dict get that handles None dicts."""
    if isinstance(d, dict):
        return d.get(key, default)
    return default


def _deep_get(d: dict | None, path: Iterable[str], default: Any = None) -> Any:
    """Safe nested get: _deep_get(x, ['a','b','c'])."""
    cur = d
    for k in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
    return cur if cur is not None else default


class DataExtractor:
    @staticmethod
    def safe_divide_and_round(
        numerator: float | None, denominator: float | int, decimal_places: int = 2
    ) -> float | None:
        n = _to_float(numerator)
        d = _to_float(denominator)
        if n is None or d in (None, 0.0):
            return None
        return round(n / d, decimal_places)

    @staticmethod
    def extract_start_time(activity_data: dict[str, Any]) -> str | None:
        try:
            summary = _dg(activity_data, "summaryDTO", {}) or {}
            start_time = summary.get("startTimeLocal") or summary.get("startTimeGMT")
            if not start_time:
                start_time = (
                    activity_data.get("startTimeLocal")
                    or activity_data.get("startTimeGMT")
                    or activity_data.get("startTime")
                )
            if not start_time:
                ts = activity_data.get("beginTimestamp")
                if isinstance(ts, (int, float)):
                    # beginTimestamp is ms epoch in many payloads
                    return datetime.fromtimestamp(ts / 1000).isoformat()
            return start_time
        except Exception:
            logger.exception("extract_start_time failed with payload keys=%s", list(activity_data or {}).keys())
            return None

    @staticmethod
    def extract_activity_type(activity_data: dict[str, Any]) -> str:
        try:
            at = _dg(activity_data, "activityType", {}) or {}
            activity_type = at.get("typeKey") or at.get("type")
            if not activity_type:
                dto = _dg(activity_data, "activityTypeDTO", {}) or {}
                activity_type = dto.get("typeKey") or dto.get("type")
            if not activity_type:
                # sometimes a plain string
                at2 = activity_data.get("activityType")
                if isinstance(at2, str):
                    activity_type = at2
            return (activity_type or "unknown").strip().lower().replace(" ", "_")
        except Exception:
            logger.exception("extract_activity_type failed")
            return "unknown"

    @staticmethod
    def convert_lactate_threshold_speed(speed_au: float | None) -> float | None:
        # Historical AU→m/s conversion used here; keep behavior, but be safe.
        f = _to_float(speed_au)
        if f is None:
            return None
        speed_ms = f * 10.0
        if speed_ms == 0:
            return None
        return _round(speed_ms, 2)

    def get_latest_sleep_duration(self, date_obj: date) -> float | None:
        try:
            sleep_data = self.garmin.client.get_sleep_data(date_obj.isoformat()) or {}
            daily_sleep = _dg(sleep_data, "dailySleepDTO", {}) or {}
            return self.safe_divide_and_round(daily_sleep.get("sleepTimeSeconds"), 3600)
        except Exception:
            logger.exception("Error getting sleep duration for %s", date_obj)
            return None

    @staticmethod
    def get_date_ranges(config: ExtractionConfig) -> dict[str, dict[str, date]]:
        end_date = date.today()
        act_days = max(0, int(getattr(config, "activities_range", 21) or 21))
        met_days = max(0, int(getattr(config, "metrics_range", 56) or 56))
        return {
            "activities": {"start": end_date - timedelta(days=act_days), "end": end_date},
            "metrics": {"start": end_date - timedelta(days=met_days), "end": end_date},
        }


class TriathlonCoachDataExtractor(DataExtractor):
    def __init__(self, email: str, password: str):
        self.garmin = GarminConnectClient()
        self.garmin.connect(email, password)

    def extract_data(self, config: ExtractionConfig = ExtractionConfig()) -> GarminData:
        date_ranges = self.get_date_ranges(config)

        data = {
            "user_profile": self.get_user_profile(),
            "daily_stats": self.get_daily_stats(date_ranges["metrics"]["end"]),
        }

        if getattr(config, "include_detailed_activities", True):
            data["recent_activities"] = self.get_recent_activities(
                date_ranges["activities"]["start"], date_ranges["activities"]["end"]
            )

        if getattr(config, "include_metrics", True):
            mstart, mend = date_ranges["metrics"]["start"], date_ranges["metrics"]["end"]
            data.update(
                {
                    "physiological_markers": self.get_physiological_markers(mstart, mend),
                    "body_metrics": self.get_body_metrics(mstart, mend),
                    "recovery_indicators": self.get_recovery_indicators(mstart, mend),
                    "training_status": self.get_training_status(mend),
                    "vo2_max_history": self.get_vo2_max_history(mstart, mend),
                    "training_load_history": self.get_training_load_history(mstart, mend),
                }
            )

        return GarminData(**data)

    # --------- User / Daily ---------

    def get_user_profile(self) -> UserProfile:
        try:
            full_profile = self.garmin.client.get_user_profile() or {}
        except Exception:
            logger.exception("get_user_profile API failed")
            full_profile = {}

        user_data = _dg(full_profile, "userData", {}) or {}
        sleep_data = _dg(full_profile, "userSleep", {}) or {}

        lt_speed_ms = self.convert_lactate_threshold_speed(user_data.get("lactateThresholdSpeed"))

        return UserProfile(
            gender=user_data.get("gender"),
            weight=_to_float(user_data.get("weight")),
            height=_to_float(user_data.get("height")),
            birth_date=user_data.get("birthDate"),
            activity_level=user_data.get("activityLevel"),
            vo2max_running=_to_float(user_data.get("vo2MaxRunning")),
            vo2max_cycling=_to_float(user_data.get("vo2MaxCycling")),
            lactate_threshold_speed=lt_speed_ms,
            lactate_threshold_heart_rate=_to_int(user_data.get("lactateThresholdHeartRate")),
            ftp_auto_detected=user_data.get("ftpAutoDetected"),
            available_training_days=user_data.get("availableTrainingDays"),
            preferred_long_training_days=user_data.get("preferredLongTrainingDays"),
            sleep_time=sleep_data.get("sleepTime"),
            wake_time=sleep_data.get("wakeTime"),
        )

    def get_daily_stats(self, date_obj: date) -> DailyStats:
        try:
            raw_data = self.garmin.client.get_stats(date_obj.isoformat()) or {}
        except Exception:
            logger.exception("get_stats API failed for %s", date_obj)
            raw_data = {}

        sleep_hours = self.get_latest_sleep_duration(date_obj)
        sleep_seconds = _to_int((sleep_hours or 0) * 3600) if sleep_hours is not None else None

        avg_stress_source = raw_data.get("averageStressLevel")
        if avg_stress_source is None:
            avg_stress_source = raw_data.get("avgWakingRespirationValue")

        return DailyStats(
            date=raw_data.get("calendarDate") or date_obj.isoformat(),
            total_steps=_to_int(raw_data.get("totalSteps")),
            total_distance_meters=_to_float(raw_data.get("totalDistanceMeters")),
            total_calories=_to_int(raw_data.get("totalKilocalories")),
            active_calories=_to_int(raw_data.get("activeKilocalories")),
            bmr_calories=_to_int(raw_data.get("bmrKilocalories")),
            wellness_start_time=raw_data.get("wellnessStartTimeLocal"),
            wellness_end_time=raw_data.get("wellnessEndTimeLocal"),
            duration_in_hours=self.safe_divide_and_round(
                _to_float(raw_data.get("durationInMilliseconds")), 3_600_000
            ),
            min_heart_rate=_to_int(raw_data.get("minHeartRate")),
            max_heart_rate=_to_int(raw_data.get("maxHeartRate")),
            resting_heart_rate=_to_int(raw_data.get("restingHeartRate")),
            average_stress_level=_to_int(avg_stress_source),
            max_stress_level=_to_int(raw_data.get("maxStressLevel")),
            stress_duration_seconds=_to_int(raw_data.get("stressDuration")),
            sleeping_seconds=sleep_seconds,
            sleeping_hours=sleep_hours,
            respiration_average=_to_float(
                raw_data.get("avgWakingRespirationValue") or raw_data.get("avgRespirationRate")
            ),
            respiration_highest=_to_float(
                raw_data.get("highestRespirationValue") or raw_data.get("maxRespirationRate")
            ),
            respiration_lowest=_to_float(
                raw_data.get("lowestRespirationValue") or raw_data.get("minRespirationRate")
            ),
        )

    # --------- Activities ---------

    def get_activity_laps(self, activity_id: int) -> list[dict[str, Any]]:
        try:
            splits = self.garmin.client.get_activity_splits(activity_id) or {}
            lap_data = splits.get("lapDTOs") or splits.get("laps") or []
            processed_laps: list[dict[str, Any]] = []
            for lap in lap_data if isinstance(lap_data, list) else []:
                if not isinstance(lap, dict):
                    continue
                dist_km = self.safe_divide_and_round(_to_float(lap.get("distance")), 1000, 2)
                dur_min = self.safe_divide_and_round(_to_float(lap.get("duration")), 60, 2)
                avg_spd_kmh = _round(_to_float(lap.get("averageSpeed")) * 3.6, 2) if _to_float(lap.get("averageSpeed")) is not None else None
                max_spd_kmh = _round(_to_float(lap.get("maxSpeed")) * 3.6, 2) if _to_float(lap.get("maxSpeed")) is not None else None

                processed = {
                    "startTime": lap.get("startTimeGMT") or lap.get("startTimeLocal"),
                    "distance": dist_km,
                    "duration": dur_min,
                    "elevationGain": _to_float(lap.get("elevationGain")),
                    "elevationLoss": _to_float(lap.get("elevationLoss")),
                    "averageSpeed": avg_spd_kmh,
                    "maxSpeed": max_spd_kmh,
                    "averageHR": _to_int(lap.get("averageHR")),
                    "maxHR": _to_int(lap.get("maxHR")),
                    "calories": _to_int(lap.get("calories")),
                    "intensity": lap.get("intensityType") or lap.get("intensity"),
                }

                # Optional power fields (cycling)
                for k_src, k_dst in [
                    ("averagePower", "averagePower"),
                    ("maxPower", "maxPower"),
                    ("minPower", "minPower"),
                    ("normalizedPower", "normalizedPower"),
                    ("totalWork", "totalWork"),
                ]:
                    if k_src in lap:
                        processed[k_dst] = _to_float(lap.get(k_src))

                processed_laps.append(processed)
            return processed_laps
        except Exception:
            logger.exception("Error fetching lap data for activity %s", activity_id)
            return []

    def get_recent_activities(self, start_date: date, end_date: date) -> list[Activity]:
        try:
            logger.info("Fetching activities between %s and %s", start_date, end_date)
            activities = self.garmin.client.get_activities_by_date(
                start_date.isoformat(), end_date.isoformat()
            ) or []
            if not isinstance(activities, list) or not activities:
                logger.warning("No activities found between %s and %s", start_date, end_date)
                return []

            focused_activities: list[Activity | dict | None] = []
            for activity in activities:
                try:
                    if not isinstance(activity, dict):
                        logger.warning("Activity entry not a dict, skipping: %s", type(activity))
                        continue

                    activity_id = activity.get("activityId") or activity.get("activityUUID")
                    if not activity_id:
                        logger.warning("Activity missing activityId, skipping. Keys: %s", list(activity.keys()))
                        continue

                    detailed_activity = self.garmin.client.get_activity(activity_id) or {}
                    if not isinstance(detailed_activity, dict) or not detailed_activity:
                        logger.warning("No details found for activity %s, skipping", activity_id)
                        continue

                    if detailed_activity.get("isMultiSportParent", False):
                        focused = self._process_multisport_activity(detailed_activity)
                    else:
                        focused = self._process_single_sport_activity(detailed_activity)

                    focused_activities.append(focused)
                except Exception:
                    logger.exception("Error processing activity %s", activity.get("activityId"))
                    continue

            valid_activities: list[Activity] = []
            for a in focused_activities:
                if a is None:
                    continue
                if isinstance(a, dict):
                    try:
                        valid_activities.append(Activity(**a))
                    except Exception:
                        logger.exception("Failed to coerce activity dict to Activity dataclass")
                elif isinstance(a, Activity):
                    valid_activities.append(a)

            logger.info(
                "Successfully processed %d out of %d activities", len(valid_activities), len(activities)
            )
            return valid_activities
        except Exception:
            logger.exception("Error fetching activities window")
            return []

    def _process_multisport_activity(self, detailed_activity: dict[str, Any]) -> Activity | None:
        try:
            activity_id = detailed_activity.get("activityId")
            if not activity_id:
                logger.warning("Multisport activity missing activityId")
                return None

            # Weather
            weather_data = None
            try:
                weather_data = self.garmin.client.get_activity_weather(activity_id)
            except Exception:
                logger.warning("Weather fetch failed for multisport activity %s", activity_id)

            # Additional details (merge shallowly)
            try:
                activity_details = self.garmin.client.get_activity_details(activity_id) or {}
                if isinstance(activity_details, dict):
                    for k, v in activity_details.items():
                        detailed_activity.setdefault(k, v)
            except Exception:
                logger.warning("Additional details fetch failed for multisport %s", activity_id)

            metadata = _dg(detailed_activity, "metadataDTO", {}) or {}
            child_ids = list(_dg(metadata, "childIds", []) or _dg(detailed_activity, "childIds", []) or [])
            child_types = _dg(metadata, "childActivityTypes", []) or []

            if not child_ids:
                # Alternative: childActivities contains dicts
                for child in _dg(detailed_activity, "childActivities", []) or []:
                    if isinstance(child, dict) and child.get("activityId"):
                        child_ids.append(child["activityId"])
                        if not child_types:
                            child_types.append(
                                _dg(child.get("activityType", {}), "typeKey", "unknown")
                            )

            if not child_ids:
                logger.warning("No child activities for multisport %s", activity_id)
                return None

            child_activities = []
            for i, child_id in enumerate(child_ids):
                try:
                    child_activity = self.garmin.client.get_activity(child_id) or {}
                    if not isinstance(child_activity, dict) or not child_activity:
                        logger.warning("Failed to fetch child activity %s", child_id)
                        continue

                    # Merge details for child
                    try:
                        child_details = self.garmin.client.get_activity_details(child_id) or {}
                        if isinstance(child_details, dict):
                            for k, v in child_details.items():
                                child_activity.setdefault(k, v)
                    except Exception:
                        logger.warning("Details fetch failed for child activity %s", child_id)

                    child_type = child_types[i] if i < len(child_types) else self.extract_activity_type(child_activity)
                    child_start_time = self.extract_start_time(child_activity)
                    child_summary = self._extract_activity_summary(_dg(child_activity, "summaryDTO", {}) or {})

                    # Cycling: top-level power fallbacks
                    if child_type == "cycling":
                        child_summary.avg_power = child_summary.avg_power or _to_float(
                            child_activity.get("avgPower") or child_activity.get("averagePower")
                        )
                        child_summary.max_power = child_summary.max_power or _to_float(child_activity.get("maxPower"))
                        child_summary.normalized_power = child_summary.normalized_power or _to_float(
                            child_activity.get("normPower") or child_activity.get("normalizedPower")
                        )
                        child_summary.training_stress_score = child_summary.training_stress_score or _to_float(
                            child_activity.get("trainingStressScore")
                        )
                        child_summary.intensity_factor = child_summary.intensity_factor or _to_float(
                            child_activity.get("intensityFactor")
                        )

                    child_lap_data = self.get_activity_laps(child_id)

                    child_activities.append(
                        {
                            "activityId": child_id,
                            "activityName": child_activity.get("activityName") or child_activity.get("name"),
                            "activityType": child_type,
                            "startTime": child_start_time,
                            "summary": child_summary,
                            "laps": child_lap_data,
                        }
                    )
                except Exception:
                    logger.exception("Error processing child activity %s", child_id)
                    continue

            if not child_activities:
                logger.warning("No valid child activities for multisport %s", activity_id)
                return None

            activity_name = (
                detailed_activity.get("activityName") or detailed_activity.get("name") or "Multisport Activity"
            )
            start_time = self.extract_start_time(detailed_activity)
            summary = self._extract_activity_summary(_dg(detailed_activity, "summaryDTO", {}) or {})

            # Pull cycling power up to parent if parent lacks it
            cycling_segments = [c for c in child_activities if c.get("activityType") == "cycling"]
            for seg in cycling_segments:
                seg_sum = seg.get("summary")
                if not isinstance(seg_sum, ActivitySummary):
                    continue
                summary.avg_power = summary.avg_power or seg_sum.avg_power
                summary.max_power = summary.max_power or seg_sum.max_power
                summary.normalized_power = summary.normalized_power or seg_sum.normalized_power
                summary.training_stress_score = summary.training_stress_score or seg_sum.training_stress_score
                summary.intensity_factor = summary.intensity_factor or seg_sum.intensity_factor

            return Activity(
                activity_id=activity_id,
                activity_type="multisport",
                activity_name=activity_name,
                start_time=start_time,
                summary=summary,
                weather=self._extract_weather_data(weather_data),
                hr_zones=[],
                # NOTE: Keeping child activities inside laps to preserve external behavior.
                laps=child_activities,
            )
        except Exception:
            logger.exception("Error processing multisport activity")
            return None

    def _process_single_sport_activity(self, detailed_activity: dict[str, Any]) -> Activity | None:
        try:
            activity_id = detailed_activity.get("activityId")
            if not activity_id:
                logger.warning("Activity missing activityId")
                return None

            try:
                activity_details = self.garmin.client.get_activity_details(activity_id) or {}
                if isinstance(activity_details, dict):
                    for k, v in activity_details.items():
                        detailed_activity.setdefault(k, v)
            except Exception:
                logger.warning("Failed to get additional details for %s", activity_id)

            weather_data = None
            try:
                weather_data = self.garmin.client.get_activity_weather(activity_id)
            except Exception:
                logger.warning("Failed to get weather data for %s", activity_id)

            lap_data = self.get_activity_laps(activity_id)

            activity_type = self.extract_activity_type(detailed_activity)
            if activity_type in ["open_water_swimming", "lap_swimming"]:
                activity_type = "swimming"

            activity_name = (
                detailed_activity.get("activityName")
                or detailed_activity.get("name")
                or f"{activity_type.replace('_', ' ').title()} Activity"
            )
            start_time = self.extract_start_time(detailed_activity)
            summary = self._extract_activity_summary(_dg(detailed_activity, "summaryDTO", {}) or {})

            if activity_type == "cycling":
                summary.avg_power = summary.avg_power or _to_float(
                    detailed_activity.get("avgPower") or detailed_activity.get("averagePower")
                )
                summary.max_power = summary.max_power or _to_float(detailed_activity.get("maxPower"))
                summary.normalized_power = summary.normalized_power or _to_float(
                    detailed_activity.get("normPower") or detailed_activity.get("normalizedPower")
                )
                summary.training_stress_score = summary.training_stress_score or _to_float(
                    detailed_activity.get("trainingStressScore")
                )
                summary.intensity_factor = summary.intensity_factor or _to_float(
                    detailed_activity.get("intensityFactor")
                )

                if (summary.avg_power is None or summary.normalized_power is None) and lap_data:
                    first_lap = lap_data[0] if isinstance(lap_data, list) and lap_data else {}
                    if isinstance(first_lap, dict):
                        summary.avg_power = summary.avg_power or _to_float(first_lap.get("averagePower"))
                        summary.normalized_power = summary.normalized_power or _to_float(
                            first_lap.get("normalizedPower")
                        )

            weather_out = None if activity_type == "meditation" else self._extract_weather_data(weather_data)
            laps_out = [] if activity_type == "meditation" else lap_data

            return Activity(
                activity_id=activity_id,
                activity_type=activity_type,
                activity_name=activity_name,
                start_time=start_time,
                summary=summary,
                weather=weather_out,
                laps=laps_out,
            )
        except Exception:
            logger.exception("Error processing single sport activity")
            return None

    # --------- Extractors / Normalizers ---------

    def _extract_activity_summary(self, summary: dict[str, Any] | None) -> ActivitySummary:
        s = summary if isinstance(summary, dict) else {}

        # More tolerant field mapping
        distance = s.get("distance") or s.get("sumDistance") or s.get("totalDistanceMeters")
        duration = s.get("duration") or s.get("sumDuration")
        moving_duration = s.get("movingDuration") or s.get("sumMovingDuration")
        elevation_gain = s.get("elevationGain") or s.get("sumElevationGain")
        elevation_loss = s.get("elevationLoss") or s.get("sumElevationLoss")
        avg_speed = s.get("averageSpeed")
        max_speed = s.get("maxSpeed")
        calories = s.get("calories") or s.get("totalKilocalories")

        avg_hr = s.get("averageHR") or s.get("avgHR")
        max_hr = s.get("maxHR")
        min_hr = s.get("minHR")

        atl = s.get("activityTrainingLoad")
        mod_min = s.get("moderateIntensityMinutes")
        vig_min = s.get("vigorousIntensityMinutes")
        rec_hr = s.get("recoveryHeartRate")

        # Respiration: accept alt keys
        avg_resp = s.get("avgRespirationRate") or s.get("avgRespirationValue")
        min_resp = s.get("minRespirationRate") or s.get("lowestRespirationValue")
        max_resp = s.get("maxRespirationRate") or s.get("highestRespirationValue")

        # Stress fallbacks
        start_stress = s.get("startStress")
        end_stress = s.get("endStress")
        avg_stress = s.get("avgStress") or s.get("averageStressLevel")
        max_stress = s.get("maxStress") or s.get("maxStressLevel")
        diff_stress = s.get("differenceStress")

        # Power-related (cycling)
        avg_power = s.get("avgPower") or s.get("averagePower")
        max_power = s.get("maxPower")
        norm_power = s.get("normPower") or s.get("normalizedPower")
        tss = s.get("trainingStressScore")
        if_factor = s.get("intensityFactor")
        avg_cadence = s.get("avgCadence")
        max_cadence = s.get("maxCadence")
        gct = s.get("avgGroundContactTime")
        vertical_oscillation = s.get("avgVerticalOscillation")
        stride_length = s.get("avgStrideLength")
        running_economy = s.get("runningEconomyScore")

        eff_ratio = None
        if s.get("averageSpeed") and s.get("avgCadence"):
            avg_speed_val = _to_float(s.get("averageSpeed"))
            avg_cadence_val = _to_float(s.get("avgCadence"))
            if avg_speed_val and avg_cadence_val:
                eff_ratio = avg_speed_val / avg_cadence_val * 60

        return ActivitySummary(
            distance=_to_float(distance),
            duration=_to_float(duration),
            moving_duration=_to_float(moving_duration),
            elevation_gain=_to_float(elevation_gain),
            elevation_loss=_to_float(elevation_loss),
            average_speed=_to_float(avg_speed),
            max_speed=_to_float(max_speed),
            calories=_to_float(calories),
            average_hr=_to_int(avg_hr),
            max_hr=_to_int(max_hr),
            min_hr=_to_int(min_hr),
            activity_training_load=_to_float(atl),
            moderate_intensity_minutes=_to_int(mod_min),
            vigorous_intensity_minutes=_to_int(vig_min),
            recovery_heart_rate=_to_int(rec_hr),
            avg_respiration_rate=_to_float(avg_resp),
            min_respiration_rate=_to_float(min_resp),
            max_respiration_rate=_to_float(max_resp),
            # Stress
            start_stress=_to_float(start_stress),
            end_stress=_to_float(end_stress),
            avg_stress=_to_float(avg_stress),
            max_stress=_to_float(max_stress),
            difference_stress=_to_float(diff_stress),
            # Power (cycling)
            avg_power=_to_float(avg_power),
            max_power=_to_float(max_power),
            normalized_power=_to_float(norm_power),
            training_stress_score=_to_float(tss),
            intensity_factor=_to_float(if_factor),
            avg_cadence=_to_int(avg_cadence),
            max_cadence=_to_int(max_cadence),
            avg_ground_contact_time=_to_float(gct),
            avg_vertical_oscillation=_to_float(vertical_oscillation),
            avg_stride_length=_to_float(stride_length),
            running_economy_score=_to_float(running_economy),
            efficiency_ratio=_to_float(eff_ratio),
        )

    def _extract_weather_data(self, weather: dict[str, Any] | None) -> WeatherData:
        if not isinstance(weather, dict):
            return WeatherData(None, None, None, None, None)
        weather_type_dto = _dg(weather, "weatherTypeDTO", {}) or {}
        weather_type = weather_type_dto.get("desc")
        return WeatherData(
            temp=_to_float(weather.get("temp")),
            apparent_temp=_to_float(weather.get("apparentTemp")),
            relative_humidity=_to_float(weather.get("relativeHumidity")),
            wind_speed=_to_float(weather.get("windSpeed")),
            weather_type=weather_type,
        )

    def _extract_hr_zone_data(self, hr_zones: list[dict[str, Any]] | None) -> list[HeartRateZone]:
        if not hr_zones or not isinstance(hr_zones, list):
            logger.debug("No heart rate zones data available or invalid format")
            return []
        processed: list[HeartRateZone] = []
        for zone in hr_zones:
            try:
                if not isinstance(zone, dict):
                    continue
                processed.append(
                    HeartRateZone(
                        zone_number=_to_int(zone.get("zoneNumber")),
                        secs_in_zone=_to_int(zone.get("secsInZone")),
                        zone_low_boundary=_to_int(zone.get("zoneLowBoundary")),
                    )
                )
            except Exception:
                logger.exception("Error processing heart rate zone item")
        return processed

    # --------- Metrics / Histories ---------

    def get_physiological_markers(self, start_date: date, end_date: date) -> PhysiologicalMarkers:
        # RHR (day)
        try:
            rhr_data = self.garmin.client.get_rhr_day(end_date.isoformat()) or {}
        except Exception:
            logger.exception("get_rhr_day failed for %s", end_date)
            rhr_data = {}

        rhr_value_list = (
            _deep_get(rhr_data, ["allMetrics", "metricsMap", "WELLNESS_RESTING_HEART_RATE"], [])
            or []
        )
        resting_heart_rate = _to_int(rhr_value_list[0].get("value")) if rhr_value_list and isinstance(rhr_value_list[0], dict) else None

        # VO2max (user summary)
        try:
            user_summary = self.garmin.client.get_user_summary(end_date.isoformat()) or {}
        except Exception:
            logger.exception("get_user_summary failed for %s", end_date)
            user_summary = {}
        vo2_max = _to_float(user_summary.get("vo2Max"))

        # HRV
        try:
            hrv_data = self.garmin.client.get_hrv_data(end_date.isoformat())
            if hrv_data is None:
                logger.warning("HRV data is None, using empty dict for hrvSummary")
                hrv_summary = {}
            else:
                hrv_summary = _dg(hrv_data, "hrvSummary", {}) or {}
        except Exception:
            logger.exception("Error fetching HRV data for %s", end_date)
            hrv_summary = {}

        baseline = _dg(hrv_summary, "baseline", {}) or {}
        hrv = {
            "weekly_avg": _to_float(hrv_summary.get("weeklyAvg")),
            "last_night_avg": _to_float(hrv_summary.get("lastNightAvg")),
            "last_night_5min_high": _to_float(hrv_summary.get("lastNight5MinHigh")),
            "baseline": {
                "low_upper": _to_float(baseline.get("lowUpper")),
                "balanced_low": _to_float(baseline.get("balancedLow")),
                "balanced_upper": _to_float(baseline.get("balancedUpper")),
            },
        }

        return PhysiologicalMarkers(resting_heart_rate=resting_heart_rate, vo2_max=vo2_max, hrv=hrv)

    def get_body_metrics(self, start_date: date, end_date: date) -> BodyMetrics:
        try:
            weight_data = self.garmin.client.get_body_composition(
                start_date.isoformat(), end_date.isoformat()
            ) or {}
        except Exception:
            logger.exception("get_body_composition failed")
            weight_data = {}

        # Hydration: fetch per-day but isolate failures
        processed_hydration_data: list[dict[str, Any]] = []
        cur = start_date
        while cur <= end_date:
            try:
                entry = self.garmin.client.get_hydration_data(cur.isoformat()) or {}
            except Exception:
                logger.warning("get_hydration_data failed for %s", cur)
                entry = {}
            goal_ml = _to_float(entry.get("goalInML"))
            value_ml = _to_float(entry.get("valueInML"))
            sweat_loss_ml = _to_float(entry.get("sweatLossInML"))
            processed_hydration_data.append(
                {
                    "date": entry.get("calendarDate") or cur.isoformat(),
                    "goal": _round((goal_ml or 0) / 1000.0, 2) if goal_ml is not None else None,
                    "intake": _round((value_ml or 0) / 1000.0, 2) if value_ml is not None else None,
                    "sweat_loss": _round((sweat_loss_ml or 0) / 1000.0, 2) if sweat_loss_ml is not None else None,
                }
            )
            cur += timedelta(days=1)

        processed_weight_data: list[dict[str, Any]] = []
        for entry in _dg(weight_data, "dateWeightList", []) or []:
            if not isinstance(entry, dict):
                continue
            weight = _to_float(entry.get("weight"))
            processed_weight_data.append(
                {
                    "date": entry.get("calendarDate"),
                    "weight": _round((weight or 0) / 1000.0, 2) if weight is not None else None,
                    "source": entry.get("sourceType"),
                }
            )

        total_average = _dg(weight_data, "totalAverage", {}) or {}
        avg_weight_g = _to_float(total_average.get("weight"))
        average_weight = _round((avg_weight_g or 0) / 1000.0, 2) if avg_weight_g is not None else None

        return BodyMetrics(
            weight={"data": processed_weight_data, "average": average_weight},
            hydration=processed_hydration_data,
        )

    def get_recovery_indicators(self, start_date: date, end_date: date) -> list[RecoveryIndicators]:
        processed_data: list[RecoveryIndicators] = []
        current_date = start_date

        while current_date <= end_date:
            try:
                sleep_data = self.garmin.client.get_sleep_data(current_date.isoformat()) or {}
                stress_data = self.garmin.client.get_stress_data(current_date.isoformat()) or {}
            except Exception:
                logger.exception("Sleep/Stress fetch failed for %s", current_date)
                sleep_data, stress_data = {}, {}

            daily_sleep = _dg(sleep_data, "dailySleepDTO", {}) or {}
            sleep_scores = _dg(daily_sleep, "sleepScores", {}) or {}

            processed_data.append(
                RecoveryIndicators(
                    date=current_date.isoformat(),
                    sleep={
                        "duration": {
                            "total": self.safe_divide_and_round(_to_float(daily_sleep.get("sleepTimeSeconds")), 3600),
                            "deep": self.safe_divide_and_round(_to_float(daily_sleep.get("deepSleepSeconds")), 3600),
                            "light": self.safe_divide_and_round(_to_float(daily_sleep.get("lightSleepSeconds")), 3600),
                            "rem": self.safe_divide_and_round(_to_float(daily_sleep.get("remSleepSeconds")), 3600),
                            "awake": self.safe_divide_and_round(_to_float(daily_sleep.get("awakeSleepSeconds")), 3600),
                        },
                        "quality": {
                            "overall_score": _deep_get(sleep_scores, ["overall", "value"]),
                            "deep_sleep": _deep_get(sleep_scores, ["deepPercentage", "value"]),
                            "rem_sleep": _deep_get(sleep_scores, ["remPercentage", "value"]),
                        },
                        "restless_moments": _to_int(sleep_data.get("restlessMomentsCount")),
                        "avg_overnight_hrv": _to_float(sleep_data.get("avgOvernightHrv")),
                        # 'hrv_status' intentionally omitted as before
                        "resting_heart_rate": _to_int(sleep_data.get("restingHeartRate")),
                    },
                    stress={
                        "max_level": _to_int(stress_data.get("maxStressLevel")),
                        "avg_level": _to_int(stress_data.get("avgStressLevel")),
                    },
                )
            )
            current_date += timedelta(days=1)

        return processed_data

    def get_training_status(self, date_obj: date) -> TrainingStatus:
        try:
            logger.info("Fetching training status for date: %s", date_obj.isoformat())
            raw_data = self.garmin.client.get_training_status(date_obj.isoformat())
        except Exception:
            logger.exception("get_training_status API failed for %s", date_obj)
            raw_data = None

        if not isinstance(raw_data, dict):
            logger.warning("Training status data missing or invalid")
            return TrainingStatus(
                vo2_max={"value": None, "date": None},
                acute_training_load={"acute_load": None, "chronic_load": None, "acwr": None},
            )

        most_recent_vo2max = raw_data.get("mostRecentVO2Max")
        vo2max_data = _dg(most_recent_vo2max, "generic", {}) if isinstance(most_recent_vo2max, dict) else None

        if vo2max_data:
            logger.info("Found VO2Max data: %s", vo2max_data)
        else:
            logger.warning("mostRecentVO2Max generic data absent")

        status = _deep_get(raw_data, ["mostRecentTrainingStatus", "latestTrainingStatusData"], {}) or {}
        status_key = next(iter(status), None) if isinstance(status, dict) and status else None
        status_data = status.get(status_key, {}) if status_key and isinstance(status, dict) else {}

        if status_key is None:
            logger.warning("No status key found in latestTrainingStatusData")
        else:
            logger.info("Found status key: %s", status_key)

        vo2max_value = _to_float(_dg(vo2max_data, "vo2MaxValue")) if vo2max_data else None
        vo2max_date = _dg(vo2max_data, "calendarDate") if vo2max_data else None
        if vo2max_value is not None or vo2max_date is not None:
            logger.info("VO2Max value: %s, date: %s", vo2max_value, vo2max_date)

        atl_dto = _dg(status_data, "acuteTrainingLoadDTO", None)
        if not isinstance(atl_dto, dict):
            logger.warning("acuteTrainingLoadDTO missing or invalid (type=%s)", type(atl_dto).__name__)
            acute_load = chronic_load = acwr = None
        else:
            acute_load = _to_float(atl_dto.get("dailyTrainingLoadAcute"))
            chronic_load = _to_float(atl_dto.get("dailyTrainingLoadChronic"))
            acwr = _to_float(atl_dto.get("dailyAcuteChronicWorkloadRatio"))
            logger.info("Training load - acute=%s chronic=%s acwr=%s", acute_load, chronic_load, acwr)

        return TrainingStatus(
            vo2_max={"value": vo2max_value, "date": vo2max_date},
            acute_training_load={"acute_load": acute_load, "chronic_load": chronic_load, "acwr": acwr},
        )

    def get_vo2_max_history(self, start_date: date, end_date: date) -> dict[str, list[dict[str, Any]]]:
        history = {"running": [], "cycling": []}
        processed_dates = {"running": set(), "cycling": set()}
        current_date = start_date
        logger.info("Fetching VO2 max history from %s to %s", start_date, end_date)

        while current_date <= end_date:
            try:
                data = self.garmin.client.get_training_status(current_date.isoformat())
                if not isinstance(data, dict):
                    current_date += timedelta(days=1)
                    continue

                mr = data.get("mostRecentVO2Max") or {}
                # Running (generic)
                gen = _dg(mr, "generic", {}) or {}
                r_val = _to_float(gen.get("vo2MaxValue"))
                r_date = gen.get("calendarDate")
                if r_val is not None and r_date and r_date not in processed_dates["running"]:
                    history["running"].append({"date": r_date, "value": r_val})
                    processed_dates["running"].add(r_date)

                # Cycling fallback search
                cyc = None
                for field in ("cycling", "bike", "cycle"):
                    if isinstance(mr, dict) and field in mr:
                        cyc = mr.get(field)
                        break
                if cyc is None and isinstance(mr, dict) and "sportSpecific" in mr:
                    ss = mr.get("sportSpecific") or {}
                    for field in ("cycling", "bike", "cycle"):
                        if field in ss:
                            cyc = ss.get(field)
                            break
                if cyc is None and isinstance(mr, dict) and isinstance(mr.get("sport"), list):
                    for entry in mr.get("sport"):
                        if isinstance(entry, dict) and "sportType" in entry:
                            st = str(entry.get("sportType", "")).lower()
                            if "cycling" in st or "bike" in st:
                                cyc = entry
                                break

                if isinstance(cyc, dict):
                    c_val = _to_float(cyc.get("vo2MaxValue"))
                    c_date = cyc.get("calendarDate")
                    if c_val is not None and c_date and c_date not in processed_dates["cycling"]:
                        history["cycling"].append({"date": c_date, "value": c_val})
                        processed_dates["cycling"].add(c_date)
            except Exception:
                logger.exception("VO2 history fetch failed for %s", current_date)

            current_date += timedelta(days=1)

        logger.info("Collected %d running and %d cycling VO2max entries",
                    len(history["running"]), len(history["cycling"]))
        return history

    def get_training_load_history(self, start_date: date, end_date: date) -> list[dict[str, Any]]:
        history: list[dict[str, Any]] = []
        current_date = start_date
        logger.info("Fetching training load history from %s to %s", start_date, end_date)

        while current_date <= end_date:
            try:
                data = self.garmin.client.get_training_status(current_date.isoformat())
                if not isinstance(data, dict):
                    current_date += timedelta(days=1)
                    continue

                latest = _deep_get(data, ["mostRecentTrainingStatus", "latestTrainingStatusData"], {}) or {}
                if not isinstance(latest, dict) or not latest:
                    current_date += timedelta(days=1)
                    continue

                status_key = next(iter(latest), None)
                status_data = latest.get(status_key, {}) if status_key else {}
                atl_dto = _dg(status_data, "acuteTrainingLoadDTO", None)
                if not isinstance(atl_dto, dict):
                    current_date += timedelta(days=1)
                    continue

                acute_load = _to_float(atl_dto.get("dailyTrainingLoadAcute"))
                chronic_load = _to_float(atl_dto.get("dailyTrainingLoadChronic"))
                acwr = _to_float(atl_dto.get("dailyAcuteChronicWorkloadRatio"))

                history.append(
                    {
                        "date": current_date.isoformat(),
                        "acute_load": acute_load,
                        "chronic_load": chronic_load,
                        "acwr": acwr,
                    }
                )
            except Exception:
                logger.exception("Training load fetch failed for %s", current_date)

            current_date += timedelta(days=1)

        logger.info("Collected %d training load history entries", len(history))
        return history
