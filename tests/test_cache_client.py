from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

from services.garmin.cache_client import CachedGarminClient


@dataclass
class FakeAPI:
    calls: dict[str, list[Any]] = field(default_factory=lambda: {})

    def _rec(self, name: str, arg: Any = None, ret: Any = None):
        self.calls.setdefault(name, []).append(arg)
        return ret

    # singleton
    def get_user_profile(self):
        return self._rec("get_user_profile", ret={"u": 1})

    # day endpoints
    def get_stats(self, day: str):
        return self._rec("get_stats", day, {"s": day})

    def get_sleep_data(self, day: str):
        return self._rec("get_sleep_data", day, {"sl": day})

    def get_stress_data(self, day: str):
        return self._rec("get_stress_data", day, {"st": day})

    def get_hrv_data(self, day: str):
        return self._rec("get_hrv_data", day, {"hrv": day})

    def get_hydration_data(self, day: str):
        return self._rec("get_hydration_data", day, {"hy": day})

    def get_training_status(self, day: str):
        return self._rec("get_training_status", day, {"ts": day})

    def get_rhr_day(self, day: str):
        return self._rec("get_rhr_day", day, {"rhr": day})

    def get_user_summary(self, day: str):
        return self._rec("get_user_summary", day, {"us": day})

    # range
    def get_activities_by_date(self, start: str, end: str):
        return self._rec(
            "get_activities_by_date",
            (start, end),
            [
                {"activityId": 1, "startTimeLocal": f"{start}T08:00:00"},
                {"activityId": 2, "summaryDTO": {"startTimeGMT": f"{end}T09:00:00"}},
                {"activityId": 3, "other": "no-date"},  # ignored shard (missing date)
            ],
        )

    # per activity
    def get_activity(self, aid: int):
        return self._rec("get_activity", aid, {"aid": aid})

    def get_activity_details(self, aid: int):
        return self._rec("get_activity_details", aid, {"details": aid})

    def get_activity_splits(self, aid: int):
        return self._rec("get_activity_splits", aid, {"splits": aid})

    def get_activity_weather(self, aid: int):
        return self._rec("get_activity_weather", aid, {"weather": aid})

    # blob range
    def get_body_composition(self, start: str, end: str):
        return self._rec("get_body_composition", (start, end), {"bc": [start, end]})


class FakeCache:
    def __init__(self, root: Path):
        self.root = root
        self.static_written: dict[str, dict] = {}
        self.days: dict[tuple[str, date], dict] = {}
        self.activities_shards: dict[date, list[dict]] = {}

    # static (singleton)
    def read_static(self, rel: str):
        return self.static_written.get(rel)

    def write_static(self, rel: str, data: dict):
        self.static_written[rel] = data
        p = self.static_path(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data))
        return p

    # day endpoints
    def read_day(self, category: str, d: date):
        return self.days.get((category, d))

    def write_day(self, category: str, d: date, data: dict):
        self.days[(category, d)] = data
        p = self.static_path(f"{category}/{d.isoformat()}.json")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data))
        return p

    # activities/day shards
    def has_day(self, category: str, d: date) -> bool:
        return (category, d) in self.days or d in self.activities_shards

    def _daterange(self, start: date, end: date):
        cur = start
        while cur <= end:
            yield cur
            cur += timedelta(days=1)

    def read_activities_for_days(self, days: list[date]) -> list[dict]:
        out: list[dict] = []
        for d in days:
            out.extend(self.activities_shards.get(d, []))
        return out

    def merge_day_list_unique(
        self, category: str, d: date, items: list[dict], id_key: str = "activityId"
    ):
        shard = self.activities_shards.setdefault(d, [])
        existing_ids = {it.get(id_key) for it in shard}
        for it in items:
            if it.get(id_key) not in existing_ids:
                shard.append(it)
                existing_ids.add(it.get(id_key))

    # per-activity files
    def static_path(self, rel: str) -> Path:
        return self.root / rel

    def _expired(self, p: Path) -> bool:
        # keep simple: never expired in tests unless explicitly deleted
        return False

    def _read_json(self, p: Path) -> dict:
        return json.loads(p.read_text())

    def _write_json(self, p: Path, data: dict):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data))


# --------------------------
# Tests
# --------------------------


def test_get_user_profile_cache_hit(tmp_path, caplog):
    api = FakeAPI()
    cache = FakeCache(tmp_path)
    cache.write_static("user/profile.json", {"cached": True})
    client = CachedGarminClient(api, cache)

    caplog.set_level("DEBUG")
    res = client.get_user_profile()

    assert res == {"cached": True}
    assert "cache hit" in caplog.text
    assert "get_user_profile" not in api.calls  # no API call


def test_get_user_profile_cache_miss_and_save(tmp_path, caplog):
    api = FakeAPI()
    cache = FakeCache(tmp_path)
    client = CachedGarminClient(api, cache)

    caplog.set_level("DEBUG")
    res = client.get_user_profile()

    assert res == {"u": 1}
    assert "cache miss" in caplog.text and "cache save" in caplog.text
    assert "get_user_profile" in api.calls
    assert cache.read_static("user/profile.json") == {"u": 1}


@pytest.mark.parametrize(
    "method, api_name, category",
    [
        ("get_stats", "get_stats", "stats"),
        ("get_sleep_data", "get_sleep_data", "sleep"),
        ("get_stress_data", "get_stress_data", "stress"),
        ("get_hrv_data", "get_hrv_data", "hrv"),
        ("get_hydration_data", "get_hydration_data", "hydration"),
        ("get_training_status", "get_training_status", "training_status"),
        ("get_rhr_day", "get_rhr_day", "rhr"),
        ("get_user_summary", "get_user_summary", "user_summary"),
    ],
)
def test_day_endpoint_cache_hit_and_miss(tmp_path, caplog, method, api_name, category):
    api = FakeAPI()
    cache = FakeCache(tmp_path)
    client = CachedGarminClient(api, cache)

    # Prime cache for hit
    d = date(2025, 10, 8)
    cache.write_day(category, d, {"cached": category})

    caplog.set_level("DEBUG")
    # Cache hit
    res_hit = getattr(client, method)(d.isoformat())
    assert res_hit == {"cached": category}
    assert f"[cache hit] {category} {d.isoformat()}" in caplog.text

    # Remove to force miss
    cache.days.pop((category, d))
    caplog.clear()

    # Cache miss -> API call -> save
    res_miss = getattr(client, method)(d.isoformat())
    assert res_miss is not None
    assert f"[cache miss] {category} {d.isoformat()}" in caplog.text
    assert api_name in api.calls


def test_get_activities_by_date_all_shards_hit(tmp_path, caplog):
    api = FakeAPI()
    cache = FakeCache(tmp_path)
    client = CachedGarminClient(api, cache)

    s, e = date(2025, 10, 1), date(2025, 10, 3)
    # Seed shards for all days
    for i, d in enumerate([s, s + timedelta(days=1), e], start=1):
        cache.activities_shards[d] = [
            {"activityId": i, "startTimeLocal": f"{d.isoformat()}T07:00:00"}
        ]

    caplog.set_level("DEBUG")
    items = client.get_activities_by_date(s.isoformat(), e.isoformat())

    assert items == [
        {"activityId": 1, "startTimeLocal": f"{s.isoformat()}T07:00:00"},
        {"activityId": 2, "startTimeLocal": f"{(s + timedelta(days=1)).isoformat()}T07:00:00"},
        {"activityId": 3, "startTimeLocal": f"{e.isoformat()}T07:00:00"},
    ]
    assert "cache hit] activities" in caplog.text
    assert "get_activities_by_date" not in api.calls


def test_get_activities_by_date_fetch_and_shard(tmp_path, caplog):
    api = FakeAPI()
    cache = FakeCache(tmp_path)
    client = CachedGarminClient(api, cache)

    s, e = "2025-10-01", "2025-10-03"

    caplog.set_level("DEBUG")
    items = client.get_activities_by_date(s, e)

    # API called once
    assert "get_activities_by_date" in api.calls and len(api.calls["get_activities_by_date"]) == 1
    # Items returned as-is
    assert any(it.get("activityId") == 1 for it in items)
    # Shards updated for two days (third item has no date and is ignored)
    from services.garmin.daily_cache import GarminDailyCache as GDC

    d1 = GDC._ensure_date(s)
    d2 = GDC._ensure_date(e)
    for d in (d1, d2):
        assert any(it.get("activityId") in (1, 2) for it in cache.activities_shards.get(d, []))
    assert "[cache save] activities shards:" in caplog.text


@pytest.mark.parametrize(
    "endpoint, api_name, filekey, payload",
    [
        ("get_activity", "get_activity", "activities/details", {"aid": 42}),
        (
            "get_activity_details",
            "get_activity_details",
            "activities/details_extra",
            {"details": 42},
        ),
        ("get_activity_splits", "get_activity_splits", "activities/splits", {"splits": 42}),
        ("get_activity_weather", "get_activity_weather", "activities/weather", {"weather": 42}),
    ],
)
def test_per_activity_cache_hit_and_miss(tmp_path, caplog, endpoint, api_name, filekey, payload):
    api = FakeAPI()
    cache = FakeCache(tmp_path)
    client = CachedGarminClient(api, cache)

    p = cache.static_path(f"{filekey}/42.json")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload))

    # Hit
    caplog.set_level("DEBUG")
    res_hit = getattr(client, endpoint)(42)
    assert res_hit == payload
    assert "[cache hit]" in caplog.text
    caplog.clear()

    # Miss -> delete file to force fetch
    p.unlink()
    res_miss = getattr(client, endpoint)(42)
    assert res_miss == payload
    assert "[cache miss]" in caplog.text and "[cache save]" in caplog.text
    assert api_name in api.calls


def test_get_body_composition_cache_hit_and_miss(tmp_path, caplog):
    api = FakeAPI()
    cache = FakeCache(tmp_path)
    client = CachedGarminClient(api, cache)

    key = "body/body_comp_2025-10-01_2025-10-08.json"
    p = cache.static_path(key)
    p.parent.mkdir(parents=True, exist_ok=True)
    data = {"bc": ["2025-10-01", "2025-10-08"]}
    p.write_text(json.dumps(data))

    # Hit
    caplog.set_level("DEBUG")
    res_hit = client.get_body_composition("2025-10-01", "2025-10-08")
    assert res_hit == data
    assert "[cache hit] body/body_comp_2025-10-01_2025-10-08.json" in caplog.text
    caplog.clear()

    # Miss
    p.unlink()
    res_miss = client.get_body_composition("2025-10-01", "2025-10-08")
    assert res_miss == {"bc": ["2025-10-01", "2025-10-08"]}
    assert "[cache miss] body/body_comp_2025-10-01_2025-10-08.json — fetching" in caplog.text
    assert "[cache save] body/body_comp_2025-10-01_2025-10-08.json" in caplog.text
