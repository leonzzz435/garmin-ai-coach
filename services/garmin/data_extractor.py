# data_extractor.py
import logging
from collections import OrderedDict
from collections.abc import Callable, Iterable, Iterator, Mapping, MutableMapping
from datetime import UTC, date, datetime, timedelta
from typing import Any, TypeVar

import requests

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
from .utils.training_metrics import TrainingMetricsCalculator

logger = logging.getLogger(__name__)

T = TypeVar("T")


def _to_float(v: Any) -> float | None:
    try:
        if v is None or isinstance(v, bool):
            return None
        return float(v)
    except Exception:
        return None


def _to_int(v: Any) -> int | None:
    try:
        if v is None or isinstance(v, bool):
            return None
        return int(v)
    except Exception:
        return None


def _round(v: Any, ndigits: int = 2) -> float | None:
    f = _to_float(v)
    return round(f, ndigits) if f is not None else None


def _dg(d: Mapping[str, Any] | None, key: str, default: Any = None) -> Any:
    return d.get(key, default) if isinstance(d, Mapping) else default


def _deep_get(d: Mapping[str, Any] | None, path: Iterable[str], default: Any = None) -> Any:
    cur = d
    for k in path:
        if not isinstance(cur, Mapping):
            return default
        cur = cur.get(k)
    return cur if cur is not None else default


def _daterange(start: date, end: date) -> Iterator[date]:
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def _merge_missing(dst: MutableMapping[str, Any], src: Mapping[str, Any] | None) -> None:
    if not src:
        return
    for k, v in src.items():
        dst.setdefault(k, v)


class DataExtractor:
    garmin: GarminConnectClient

    @staticmethod
    def safe_divide_and_round(
        numerator: float | None, denominator: float, decimal_places: int = 2
    ) -> float | None:
        n = _to_float(numerator)
        d = _to_float(denominator)
        if n is None or d is None or d == 0.0:
            return None
        return round(n / d, decimal_places)

    @staticmethod
    def extract_start_time(activity_data: Mapping[str, Any]) -> str | None:
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
                    return datetime.fromtimestamp(ts / 1000, tz=UTC).isoformat()
            return start_time
        except Exception:
            logger.exception(
                "extract_start_time failed with payload keys=%s",
                list((activity_data or {}).keys()),
            )
            return None

    @staticmethod
    def extract_activity_type(activity_data: Mapping[str, Any]) -> str:
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
        lt_days = max(0, int(getattr(config, "long_term_range", 360) or 360))
        return {
            "activities": {"start": end_date - timedelta(days=act_days), "end": end_date},
            "metrics": {"start": end_date - timedelta(days=met_days), "end": end_date},
            "long_term": {"start": end_date - timedelta(days=lt_days), "end": end_date},
        }


class TriathlonCoachDataExtractor(DataExtractor):
    def __init__(self, email: str, password: str):
        self.garmin = GarminConnectClient()
        self.garmin.connect(email, password)
        self._training_status_cache: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._training_status_cache_max = 1024

    def _call_api(self, fn: Callable[..., T], *args, default: Any, what: str) -> Any:
        try:
            result = fn(*args)
            return result if result is not None else default
        except (requests.HTTPError, requests.RequestException, RuntimeError, TypeError, ValueError):
            logger.exception("API failed: %s", what)
            return default

    def _training_status_cached(self, day_iso: str) -> dict[str, Any]:
        cache = self._training_status_cache
        if day_iso in cache:
            cache.move_to_end(day_iso)
            return cache[day_iso]

        result = self._call_api(
            self.garmin.client.get_training_status,
            day_iso,
            default={},
            what=f"get_training_status({day_iso})",
        )
        if result is None:
            # Should technically be empty dict given default={},
            # but safety first if API returns None and default is used.
            result = {}

        cache[day_iso] = result
        cache.move_to_end(day_iso)
        if len(cache) > self._training_status_cache_max:
            cache.popitem(last=False)
        return result

    def _get_activity_details(self, activity_id: Any) -> dict[str, Any] | None:
        detailed_activity = self._call_api(
            self.garmin.client.get_activity,
            activity_id,
            default={},
            what=f"get_activity({activity_id})",
        )
        if not isinstance(detailed_activity, dict) or not detailed_activity:
            return None
        return detailed_activity

    def _coerce_activities(self, focused_activities: list[Activity | dict | None]) -> list[Activity]:
        valid_activities: list[Activity] = []
        for activity in focused_activities:
            if activity is None:
                continue
            if isinstance(activity, Mapping):
                try:
                    valid_activities.append(Activity(**activity))
                except (TypeError, ValueError):
                    logger.exception("Failed to coerce activity dict to Activity dataclass")
            elif isinstance(activity, Activity):
                valid_activities.append(activity)
        return valid_activities

    @staticmethod
    def _first_mapping_value_by_keys(container: Any, keys: tuple[str, ...]) -> Mapping[str, Any] | None:
        if not isinstance(container, Mapping):
            return None
        for key in keys:
            value = container.get(key)
            if isinstance(value, Mapping):
                return value
        return None

    @staticmethod
    def _is_cycling_sport_type(value: Any) -> bool:
        sport_type = str(value or "").lower()
        return "cycling" in sport_type or "bike" in sport_type

    @classmethod
    def _cycling_candidate_from_most_recent(cls, most_recent: Mapping[str, Any]) -> Mapping[str, Any] | None:
        keys = ("cycling", "bike", "cycle")
        cycling = cls._first_mapping_value_by_keys(most_recent, keys)
        if cycling:
            return cycling

        cycling = cls._first_mapping_value_by_keys(most_recent.get("sportSpecific"), keys)
        if cycling:
            return cycling

        sport_list = most_recent.get("sport")
        if not isinstance(sport_list, list):
            return None
        for entry in sport_list:
            if not isinstance(entry, Mapping):
                continue
            if cls._is_cycling_sport_type(entry.get("sportType")):
                return entry
        return None

    @staticmethod
    def _extract_sport_specific_vo2max(most_recent: Any) -> dict[str, float | str] | None:
        if not isinstance(most_recent, Mapping):
            return None

        cycling = TriathlonCoachDataExtractor._cycling_candidate_from_most_recent(most_recent)
        if not cycling:
            return None

        value = _to_float(cycling.get("vo2MaxValue"))
        date_ = cycling.get("calendarDate")
        if value is None or not date_:
            return None
        return {"date": date_, "value": value}

    @staticmethod
    def _enrich_cycling_power(payload: Mapping[str, Any], summary: ActivitySummary):
        summary.avg_power = summary.avg_power or _to_float(
            payload.get("avgPower") or payload.get("averagePower")
        )
        summary.max_power = summary.max_power or _to_float(payload.get("maxPower"))
        summary.normalized_power = summary.normalized_power or _to_float(
            payload.get("normPower") or payload.get("normalizedPower")
        )
        summary.training_stress_score = summary.training_stress_score or _to_float(
            payload.get("trainingStressScore")
        )
        summary.intensity_factor = summary.intensity_factor or _to_float(
            payload.get("intensityFactor")
        )

    def extract_data(self, config: ExtractionConfig | None = None) -> GarminData:
        config = config or ExtractionConfig()
        date_ranges = self.get_date_ranges(config)

        data: dict[str, Any] = {
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

        if getattr(config, "include_long_term_trends", True):
            lt_start, lt_end = date_ranges["long_term"]["start"], date_ranges["long_term"]["end"]
            lt_interval = getattr(config, "long_term_interval", 14) or 14
            data.update(
                {
                    "long_term_vo2_max_trend": self.get_long_term_vo2_max_trend(lt_start, lt_end, lt_interval),
                    "long_term_training_load_trend": self.get_long_term_training_load_trend(
                        lt_start, lt_end, lt_interval
                    ),
                }
            )

        return GarminData(**data)

    # --------- User / Daily ---------

    def get_user_profile(self) -> UserProfile:
        full_profile = self._call_api(
            self.garmin.client.get_user_profile,
            default={},
            what="get_user_profile",
        ) or {}

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
        raw_data: dict[str, Any] = self._call_api(
            self.garmin.client.get_stats,
            date_obj.isoformat(),
            default={},
            what=f"get_stats({date_obj})",
        )

        sleep_hours = self.get_latest_sleep_duration(date_obj)
        sleep_seconds = _to_int((sleep_hours or 0) * 3600) if sleep_hours is not None else None

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
                _to_float(raw_data.get("durationInMilliseconds")),
                3_600_000,
            ),
            min_heart_rate=_to_int(raw_data.get("minHeartRate")),
            max_heart_rate=_to_int(raw_data.get("maxHeartRate")),
            resting_heart_rate=_to_int(raw_data.get("restingHeartRate")),
            average_stress_level=_to_int(raw_data.get("avgWakingRespirationValue"))  # kept original mapping
            if raw_data.get("averageStressLevel") is None
            else _to_int(raw_data.get("averageStressLevel")),
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
            respiration_lowest=_to_float(raw_data.get("lowestRespirationValue") or raw_data.get("minRespirationRate")),
        )

    # --------- Activities ---------

    def get_activity_laps(self, activity_id: int) -> list[dict[str, Any]]:
        splits = self._call_api(
            self.garmin.client.get_activity_splits,
            activity_id,
            default={},
            what=f"get_activity_splits({activity_id})"
        ) or {}
        lap_data = splits.get("lapDTOs") or splits.get("laps") or []
        processed_laps: list[dict[str, Any]] = []
        for lap in lap_data if isinstance(lap_data, list) else []:
            if not isinstance(lap, Mapping):
                continue
            dist_km = self.safe_divide_and_round(_to_float(lap.get("distance")), 1000, 2)
            dur_min = self.safe_divide_and_round(_to_float(lap.get("duration")), 60, 2)

            avg_speed_ms = _to_float(lap.get("averageSpeed"))
            avg_spd_kmh = _round(avg_speed_ms * 3.6, 2) if avg_speed_ms is not None else None

            max_speed_ms = _to_float(lap.get("maxSpeed"))
            max_spd_kmh = _round(max_speed_ms * 3.6, 2) if max_speed_ms is not None else None

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

    def get_recent_activities(self, start_date: date, end_date: date) -> list[Activity]:
        logger.info("Fetching activities between %s and %s", start_date, end_date)
        activities = self._call_api(
            self.garmin.client.get_activities_by_date,
            start_date.isoformat(), end_date.isoformat(),
            default=[],
            what=f"get_activities_by_date({start_date}, {end_date})",
        ) or []
        if not isinstance(activities, list) or not activities:
            logger.warning("No activities found between %s and %s", start_date, end_date)
            return []

        focused_activities: list[Activity | dict | None] = []
        for activity in activities:
            if not isinstance(activity, Mapping):
                continue

            activity_id = activity.get("activityId") or activity.get("activityUUID")
            if not activity_id:
                logger.warning("Activity missing activityId, skipping. Keys: %s", list(activity.keys()))
                continue

            detailed_activity: dict[str, Any] | None = self._get_activity_details(activity_id)
            if not detailed_activity:
                logger.warning("No details found for activity %s, skipping", activity_id)
                continue

            if detailed_activity.get("isMultiSportParent", False):
                focused = self._process_multisport_activity(detailed_activity)
            else:
                focused = self._process_single_sport_activity(detailed_activity)

            focused_activities.append(focused)

        valid_activities = self._coerce_activities(focused_activities)
        logger.info("Successfully processed %d out of %d activities", len(valid_activities), len(activities))
        return valid_activities

    def _fetch_activity_weather(self, activity_id: Any) -> Any:
        return self._call_api(
            self.garmin.client.get_activity_weather,
            activity_id,
            default=None,
            what=f"get_activity_weather({activity_id})",
        )

    def _merge_activity_details_in_place(self, activity_id: Any, activity: MutableMapping[str, Any]):
        details = self._call_api(
            self.garmin.client.get_activity_details,
            activity_id,
            default={},
            what=f"get_activity_details({activity_id})",
        ) or {}
        _merge_missing(activity, details)

    def _multisport_child_ids_and_types(self, activity: Mapping[str, Any]) -> tuple[list[Any], list[Any]]:
        metadata = _dg(activity, "metadataDTO", {}) or {}
        child_ids = list(_dg(metadata, "childIds", []) or _dg(activity, "childIds", []) or [])
        child_types = list(_dg(metadata, "childActivityTypes", []) or [])

        if child_ids:
            return child_ids, child_types

        for child in _dg(activity, "childActivities", []) or []:
            if not isinstance(child, Mapping):
                continue
            child_id = child.get("activityId")
            if not child_id:
                continue
            child_ids.append(child_id)
            if not child_types:
                child_types.append(_dg(child.get("activityType", {}), "typeKey", "unknown"))

        return child_ids, child_types

    def _fetch_child_activity_with_details(self, activity_id: Any) -> dict[str, Any] | None:
        child_activity: dict[str, Any] | None = self._call_api(
            self.garmin.client.get_activity,
            activity_id,
            default={},
            what=f"get_activity({activity_id})",
        )
        if not isinstance(child_activity, dict) or not child_activity:
            logger.warning("Failed to fetch child activity %s", activity_id)
            return None

        details = self._call_api(
            self.garmin.client.get_activity_details,
            activity_id,
            default={},
            what=f"get_activity_details({activity_id})",
        ) or {}
        _merge_missing(child_activity, details)

        return child_activity

    def _build_multisport_child_entry(
        self,
        child_id: Any,
        child_activity: dict[str, Any],
        child_type: Any,
    ) -> dict[str, Any]:
        child_start_time = self.extract_start_time(child_activity)
        child_summary = self._extract_activity_summary(_dg(child_activity, "summaryDTO", {}) or {})
        if child_type == "cycling":
            self._enrich_cycling_power(child_activity, child_summary)

        return {
            "activityId": child_id,
            "activityName": child_activity.get("activityName") or child_activity.get("name"),
            "activityType": child_type,
            "startTime": child_start_time,
            "summary": child_summary,
            "laps": self.get_activity_laps(child_id),
        }

    def _multisport_child_entries(self, child_ids: list[Any], child_types: list[Any]) -> list[dict[str, Any]]:
        child_activities = []
        for i, child_id in enumerate(child_ids):
            child_activity = self._fetch_child_activity_with_details(child_id)
            if not child_activity:
                continue

            child_type = child_types[i] if i < len(child_types) else self.extract_activity_type(child_activity)
            child_activities.append(
                self._build_multisport_child_entry(
                    child_id=child_id,
                    child_activity=child_activity,
                    child_type=child_type,
                )
            )
        return child_activities

    @staticmethod
    def _apply_multisport_cycling_power(summary: ActivitySummary, child_activities: list[dict[str, Any]]):
        for seg in child_activities:
            if seg.get("activityType") != "cycling":
                continue
            seg_sum = seg.get("summary")
            if not isinstance(seg_sum, ActivitySummary):
                continue
            summary.avg_power = summary.avg_power or seg_sum.avg_power
            summary.max_power = summary.max_power or seg_sum.max_power
            summary.normalized_power = summary.normalized_power or seg_sum.normalized_power
            summary.training_stress_score = summary.training_stress_score or seg_sum.training_stress_score
            summary.intensity_factor = summary.intensity_factor or seg_sum.intensity_factor

    def _process_multisport_activity(self, detailed_activity: MutableMapping[str, Any]) -> Activity | None:
        try:
            activity_id = detailed_activity.get("activityId")
            if not activity_id:
                logger.warning("Multisport activity missing activityId")
                return None

            weather_data = self._fetch_activity_weather(activity_id)
            self._merge_activity_details_in_place(activity_id, detailed_activity)

            child_ids, child_types = self._multisport_child_ids_and_types(detailed_activity)
            if not child_ids:
                logger.warning("No child activities for multisport %s", activity_id)
                return None

            child_activities = self._multisport_child_entries(child_ids, child_types)
            if not child_activities:
                logger.warning("No valid child activities for multisport %s", activity_id)
                return None

            activity_name = detailed_activity.get("activityName") or detailed_activity.get("name") or "Multisport Activity"
            start_time = self.extract_start_time(detailed_activity)
            summary = self._extract_activity_summary(_dg(detailed_activity, "summaryDTO", {}) or {})
            self._apply_multisport_cycling_power(summary, child_activities)

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

    def _process_single_sport_activity(self, detailed_activity: MutableMapping[str, Any]) -> Activity | None:
        try:
            activity_id = detailed_activity.get("activityId")
            if not activity_id:
                logger.warning("Activity missing activityId")
                return None

            activity_details = self._call_api(
                self.garmin.client.get_activity_details,
                activity_id,
                default={},
                what=f"get_activity_details({activity_id})"
            ) or {}
            _merge_missing(detailed_activity, activity_details)

            weather_data = self._call_api(
                self.garmin.client.get_activity_weather,
                activity_id,
                default=None,
                what=f"get_activity_weather({activity_id})"
            )

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
                self._enrich_cycling_power(detailed_activity, summary)

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

    def _extract_activity_summary(self, summary: Mapping[str, Any] | None) -> ActivitySummary:
        s = summary if isinstance(summary, Mapping) else {}

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

        return ActivitySummary(
            distance=_to_float(distance),
            duration=_to_int(duration),
            moving_duration=_to_int(moving_duration),
            elevation_gain=_to_float(elevation_gain),
            elevation_loss=_to_float(elevation_loss),
            average_speed=_to_float(avg_speed),
            max_speed=_to_float(max_speed),
            calories=_to_int(calories),
            average_hr=_to_int(avg_hr),
            max_hr=_to_int(max_hr),
            min_hr=_to_int(min_hr),
            activity_training_load=_to_int(atl),
            moderate_intensity_minutes=_to_int(mod_min),
            vigorous_intensity_minutes=_to_int(vig_min),
            recovery_heart_rate=_to_int(rec_hr),
            # Respiration
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
        )

    def _extract_weather_data(self, weather: Mapping[str, Any] | None) -> WeatherData:
        if not isinstance(weather, Mapping):
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

    def _extract_hr_zone_data(self, hr_zones: list[Any] | None) -> list[HeartRateZone]:
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
        rhr_data = self._call_api(
            self.garmin.client.get_rhr_day,
            end_date.isoformat(),
            default={},
            what=f"get_rhr_day({end_date})"
        ) or {}

        rhr_value_list = _deep_get(rhr_data, ["allMetrics", "metricsMap", "WELLNESS_RESTING_HEART_RATE"], []) or []
        resting_heart_rate = (
            _to_int(rhr_value_list[0].get("value")) if rhr_value_list and isinstance(rhr_value_list[0], dict) else None
        )

        user_summary = self._call_api(
            self.garmin.client.get_user_summary,
            end_date.isoformat(),
            default={},
            what=f"get_user_summary({end_date})"
        ) or {}
        vo2_max = _to_float(user_summary.get("vo2Max"))

        hrv_data = self._call_api(
            self.garmin.client.get_hrv_data,
            end_date.isoformat(),
            default={},
            what=f"get_hrv_data({end_date})"
        ) or {}
        hrv_summary = _dg(hrv_data, "hrvSummary", {}) or {}

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
        weight_data: dict[str, Any] | None = self._call_api(
            self.garmin.client.get_body_composition,
            start_date.isoformat(), end_date.isoformat(),
            default={},
            what="get_body_composition"
        )

        processed_hydration_data: list[dict[str, Any]] = []
        for cur in _daterange(start_date, end_date):
            entry: dict[str, Any] | None = self._call_api(
                self.garmin.client.get_hydration_data,
                cur.isoformat(),
                default={},
                what=f"get_hydration_data({cur})"
            )
            if not entry:
                continue
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

        processed_weight_data: list[dict[str, Any]] = []
        for entry in _dg(weight_data, "dateWeightList", []) or []:
            if not isinstance(entry, dict):
                continue
            weight = _to_float(entry.get("weight"))
            processed_weight_data.append(
                {
                    "date": entry.get("calendarDate"),
                    "weight": _round((weight or 0) / 1000.0, 2) if weight is not None else None,  # kg
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

        for current_date in _daterange(start_date, end_date):
            sleep_data: dict[str, Any] = self._call_api(
                self.garmin.client.get_sleep_data,
                current_date.isoformat(),
                default={},
                what=f"get_sleep_data({current_date})"
            )

            stress_data: dict[str, Any] = self._call_api(
                self.garmin.client.get_stress_data,
                current_date.isoformat(),
                default={},
                what=f"get_stress_data({current_date})"
            )

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

        return processed_data

    def get_training_status(self, date_obj: date) -> TrainingStatus:
        logger.debug("Fetching training status for date: %s", date_obj.isoformat())
        raw_data = self._training_status_cached(date_obj.isoformat())



        most_recent_vo2max = raw_data.get("mostRecentVO2Max")
        vo2max_data = _dg(most_recent_vo2max, "generic", {}) if isinstance(most_recent_vo2max, dict) else None

        if vo2max_data:
            logger.debug("Found VO2Max data: %s", vo2max_data)
        else:
            logger.warning("mostRecentVO2Max generic data absent")

        status = _deep_get(raw_data, ["mostRecentTrainingStatus", "latestTrainingStatusData"], {}) or {}
        status_key = next(iter(status), None) if isinstance(status, dict) and status else None
        status_data = status.get(status_key, {}) if status_key and isinstance(status, dict) else {}

        if status_key is None:
            logger.warning("No status key found in latestTrainingStatusData")
        else:
            logger.debug("Found status key: %s", status_key)

        vo2max_value = _to_float(_dg(vo2max_data, "vo2MaxValue")) if vo2max_data else None
        vo2max_date = _dg(vo2max_data, "calendarDate") if vo2max_data else None
        if vo2max_value is not None or vo2max_date is not None:
            logger.debug("VO2Max value: %s, date: %s", vo2max_value, vo2max_date)

        atl_dto = _dg(status_data, "acuteTrainingLoadDTO", None)
        if not isinstance(atl_dto, dict):
            logger.warning("acuteTrainingLoadDTO missing or invalid (type=%s)", type(atl_dto).__name__)
            acute_load = chronic_load = acwr = None
        else:
            acute_load = _to_float(atl_dto.get("dailyTrainingLoadAcute"))
            chronic_load = _to_float(atl_dto.get("dailyTrainingLoadChronic"))
            acwr = _to_float(atl_dto.get("dailyAcuteChronicWorkloadRatio"))
            logger.debug("Training load - acute=%s chronic=%s acwr=%s", acute_load, chronic_load, acwr)

        return TrainingStatus(
            vo2_max={"value": vo2max_value, "date": vo2max_date},
            acute_training_load={"acute_load": acute_load, "chronic_load": chronic_load, "acwr": acwr},
        )

    def get_vo2_max_history(self, start_date: date, end_date: date) -> dict[str, list[dict[str, Any]]]:
        history: dict[str, list[dict[str, Any]]] = {"running": [], "cycling": []}
        processed_dates: dict[str, set[str]] = {"running": set(), "cycling": set()}
        logger.debug("Fetching VO2 max history from %s to %s", start_date, end_date)

        for current_date in _daterange(start_date, end_date):
            data: Any = self._training_status_cached(current_date.isoformat())
            if not isinstance(data, dict):
                continue

            mr = data.get("mostRecentVO2Max") or {}
            gen = _dg(mr, "generic", {}) or {}
            r_val = _to_float(gen.get("vo2MaxValue"))
            r_date = gen.get("calendarDate")
            if r_val is not None and r_date and r_date not in processed_dates["running"]:
                history["running"].append({"date": r_date, "value": r_val})
                processed_dates["running"].add(r_date)

            cycling = self._extract_sport_specific_vo2max(mr)
            if cycling and cycling["date"] not in processed_dates["cycling"]:
                history["cycling"].append(cycling)
                processed_dates["cycling"].add(str(cycling["date"]))

        logger.info(
            "Collected %d running and %d cycling VO2max entries", len(history["running"]), len(history["cycling"])
        )
        return history


    def get_long_term_vo2_max_trend(
        self, start_date: date, end_date: date, interval_days: int = 14
    ) -> dict[str, list[dict[str, Any]]]:
        trend: dict[str, list[dict[str, Any]]] = {"running": [], "cycling": []}
        processed_dates: dict[str, set[str]] = {"running": set(), "cycling": set()}
        sample_dates = self._generate_sample_dates(start_date, end_date, interval_days)
        logger.debug(
            "Fetching long-term VO2 max trend: %d sample dates from %s to %s", len(sample_dates), start_date, end_date
        )

        for sample_date in sample_dates:
            data: Any = self._training_status_cached(sample_date.isoformat())
            if not isinstance(data, dict):
                continue

            mr = data.get("mostRecentVO2Max") or {}

            gen = _dg(mr, "generic", {}) or {}
            r_val = _to_float(gen.get("vo2MaxValue"))
            r_date = gen.get("calendarDate")
            if r_val is not None and r_date and r_date not in processed_dates["running"]:
                trend["running"].append({"date": r_date, "value": r_val})
                processed_dates["running"].add(r_date)

            cycling = self._extract_sport_specific_vo2max(mr)
            if cycling and cycling["date"] not in processed_dates["cycling"]:
                trend["cycling"].append(cycling)
                processed_dates["cycling"].add(str(cycling["date"]))

        trend["running"].sort(key=lambda x: x["date"])
        trend["cycling"].sort(key=lambda x: x["date"])
        logger.info(
            "Collected %d running and %d cycling long-term VO2 max entries",
            len(trend["running"]),
            len(trend["cycling"]),
        )
        return trend

    def get_long_term_training_load_trend(
        self, start_date: date, end_date: date, interval_days: int = 14
    ) -> list[dict[str, Any]]:
        trend: list[dict[str, Any]] = []
        sample_dates = self._generate_sample_dates(start_date, end_date, interval_days)
        logger.debug(
            "Fetching long-term training load trend: %d sample dates from %s to %s",
            len(sample_dates),
            start_date,
            end_date,
        )

        for sample_date in sample_dates:
            data: Any = self._training_status_cached(sample_date.isoformat())
            if not isinstance(data, dict):
                continue

            latest = _deep_get(data, ["mostRecentTrainingStatus", "latestTrainingStatusData"], {}) or {}
            if not isinstance(latest, dict) or not latest:
                continue

            status_key = next(iter(latest), None)
            status_data = latest.get(status_key, {}) if status_key else {}
            atl_dto = _dg(status_data, "acuteTrainingLoadDTO", None)
            if not isinstance(atl_dto, dict):
                continue

            chronic_load = _to_float(atl_dto.get("dailyTrainingLoadChronic"))
            if chronic_load is not None:
                trend.append({"date": sample_date.isoformat(), "chronic_load": chronic_load})

        trend.sort(key=lambda x: x["date"])
        logger.info("Collected %d long-term training load entries", len(trend))
        return trend

    @staticmethod
    def _parse_local_date(start_time: str | None) -> date | None:
        if not start_time or not isinstance(start_time, str):
            return None
        s = start_time.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(s)
            return dt.date()
        except ValueError:
            try:
                return date.fromisoformat(s[:10])
            except ValueError:
                return None

    def get_daily_activity_loads(self, start_date: date, end_date: date) -> dict[str, float]:
        loads = {d.isoformat(): 0.0 for d in _daterange(start_date, end_date)}

        activities: list[Any] = self._call_api(
            self.garmin.client.get_activities_by_date,
            start_date.isoformat(), end_date.isoformat(),
            default=[],
            what=f"get_activities_by_date({start_date}, {end_date})"
        )



        for a in activities:
            if not isinstance(a, Mapping):
                continue

            if a.get("parentActivityId"):
                continue

            st = self.extract_start_time(a)
            d = self._parse_local_date(st)
            if d is None:
                d_str = a.get("calendarDate")
                try:
                    d = date.fromisoformat(d_str) if isinstance(d_str, str) else None
                except ValueError:
                    d = None
            if d is None:
                continue

            key = d.isoformat()
            if key not in loads:
                continue

            load = (
                _to_float(a.get("activityTrainingLoad"))
                or _to_float(_deep_get(a, ["summaryDTO", "activityTrainingLoad"]))
                or 0.0
            )
            loads[key] = float(loads.get(key, 0.0) + (load or 0.0))

        return loads



    def get_training_load_history(
        self,
        start_date: date,
        end_date: date,
        acute_span: int = 7,
        chronic_span: int = 28,
        uncouple_days: int = 7,
        eps: float = 1e-6,
    ) -> list[dict[str, Any]]:
        warmup_days = chronic_span * 2
        fetch_start = start_date - timedelta(days=warmup_days)
        loads_map = self.get_daily_activity_loads(fetch_start, end_date)

        calculator = TrainingMetricsCalculator(daily_loads=loads_map)
        return calculator.calculate_metrics(
            start_date=start_date,
            end_date=end_date,
            acute_span=acute_span,
            chronic_span=chronic_span,
            uncouple_days=uncouple_days,
        )

    @staticmethod
    def _generate_sample_dates(start_date: date, end_date: date, interval_days: int) -> list[date]:
        sample_dates = []
        current_date = end_date
        while current_date >= start_date:
            sample_dates.append(current_date)
            current_date -= timedelta(days=interval_days)
        return sample_dates
