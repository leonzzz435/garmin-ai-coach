import logging
from typing import Any

from services.garmin.daily_cache import GarminDailyCache


class CachedGarminClient:
    def __init__(self, api: Any, cache: GarminDailyCache):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.api = api
        self.cache = cache

    def get_user_profile(self) -> dict | None:
        rel = "user/profile.json"
        cached = self.cache.read_static(rel)
        if cached is not None:
            self.logger.debug("[cache hit] %s", rel)
            return cached
        self.logger.debug("[cache miss] %s — fetching", rel)
        data = self.api.get_user_profile()
        if data is not None:
            path = self.cache.write_static(rel, data)
            self.logger.debug("[cache save] %s -> %s", rel, path)
        return data

    def _day_get(self, category: str, day_iso: str, fetch_fn) -> dict | None:
        d = GarminDailyCache._ensure_date(day_iso)
        if (cached := self.cache.read_day(category, d)) is not None:
            self.logger.debug("[cache hit] %s %s", category, d.isoformat())
            return cached
        self.logger.debug("[cache miss] %s %s — fetching", category, d.isoformat())
        data = fetch_fn(d.isoformat())
        if data is not None:
            path = self.cache.write_day(category, d, data)
            self.logger.debug("[cache save] %s %s -> %s", category, d.isoformat(), path)
        return data

    def get_stats(self, day_iso: str) -> dict | None:
        return self._day_get("stats", day_iso, self.api.get_stats)

    def get_sleep_data(self, day_iso: str) -> dict | None:
        return self._day_get("sleep", day_iso, self.api.get_sleep_data)

    def get_stress_data(self, day_iso: str) -> dict | None:
        return self._day_get("stress", day_iso, self.api.get_stress_data)

    def get_hrv_data(self, day_iso: str) -> dict | None:
        return self._day_get("hrv", day_iso, self.api.get_hrv_data)

    def get_hydration_data(self, day_iso: str) -> dict | None:
        return self._day_get("hydration", day_iso, self.api.get_hydration_data)

    def get_training_status(self, day_iso: str) -> dict | None:
        return self._day_get("training_status", day_iso, self.api.get_training_status)

    def get_rhr_day(self, day_iso: str) -> dict | None:
        return self._day_get("rhr", day_iso, self.api.get_rhr_day)

    def get_user_summary(self, day_iso: str) -> dict | None:
        return self._day_get("user_summary", day_iso, self.api.get_user_summary)

    def get_activities_by_date(self, start_iso: str, end_iso: str) -> list[dict]:
        start = GarminDailyCache._ensure_date(start_iso)
        end = GarminDailyCache._ensure_date(end_iso)
        days = list(self.cache._daterange(start, end))

        if all(self.cache.has_day("activities/day", d) for d in days):
            self.logger.debug(
                "[cache hit] activities %s..%s — composing from %d day shard(s)",
                start.isoformat(),
                end.isoformat(),
                len(days),
            )
            return self.cache.read_activities_for_days(days)

        self.logger.debug(
            "[cache miss] activities %s..%s — fetching and sharding per-day",
            start.isoformat(),
            end.isoformat(),
        )
        items = self.api.get_activities_by_date(start.isoformat(), end.isoformat()) or []
        shard_counts: dict[str, int] = {}
        for it in items:
            day_str = None
            if isinstance(it, dict):
                day_str = (
                    it.get("startTimeLocal")
                    or it.get("startTimeGMT")
                    or (it.get("summaryDTO", {}) or {}).get("startTimeLocal")
                    or (it.get("summaryDTO", {}) or {}).get("startTimeGMT")
                )
            try:
                d = GarminDailyCache._ensure_date(day_str) if day_str else None
            except Exception:
                d = None
            if d is None:
                continue
            self.cache.merge_day_list_unique("activities/day", d, [it], id_key="activityId")
            shard_counts[d.isoformat()] = shard_counts.get(d.isoformat(), 0) + 1

        if shard_counts:
            self.logger.debug(
                "[cache save] activities shards: %d day file(s) updated: %s",
                len(shard_counts),
                ", ".join(sorted(shard_counts.keys())),
            )
        return items

    def _read_or_fetch_activity(self, category: str, activity_id: int, fetch_fn) -> dict | None:
        p = self.cache.static_path(f"activities/{category}/{int(activity_id)}.json")
        if p.exists() and not self.cache._expired(p):
            self.logger.debug("[cache hit] activities/%s id=%s", category, activity_id)
            return self.cache._read_json(p)
        self.logger.debug("[cache miss] activities/%s id=%s — fetching", category, activity_id)
        data = fetch_fn(activity_id)
        if data is not None:
            self.cache._write_json(p, data)
            self.logger.debug("[cache save] activities/%s id=%s -> %s", category, activity_id, p)
        return data

    def get_activity(self, activity_id: int) -> dict | None:
        return self._read_or_fetch_activity("details", activity_id, self.api.get_activity)

    def get_activity_details(self, activity_id: int) -> dict | None:
        return self._read_or_fetch_activity(
            "details_extra", activity_id, self.api.get_activity_details
        )

    def get_activity_splits(self, activity_id: int) -> dict | None:
        return self._read_or_fetch_activity("splits", activity_id, self.api.get_activity_splits)

    def get_activity_weather(self, activity_id: int) -> dict | None:
        return self._read_or_fetch_activity("weather", activity_id, self.api.get_activity_weather)

    def get_body_composition(self, start_iso: str, end_iso: str) -> dict | None:
        key = f"body/body_comp_{start_iso}_{end_iso}.json"
        p = self.cache.static_path(key)
        if p.exists() and not self.cache._expired(p):
            self.logger.debug("[cache hit] %s", key)
            return self.cache._read_json(p)
        self.logger.debug("[cache miss] %s — fetching", key)
        data = self.api.get_body_composition(start_iso, end_iso)
        if data is not None:
            self.cache._write_json(p, data)
            self.logger.debug("[cache save] %s -> %s", key, p)
        return data
