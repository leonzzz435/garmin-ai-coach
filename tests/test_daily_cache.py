import json
import os
from datetime import date, datetime, timedelta

import pytest

from services.garmin.daily_cache import GarminDailyCache


@pytest.fixture
def cache(tmp_path) -> GarminDailyCache:
    return GarminDailyCache(tmp_path / "garmin_cache")


class TestEnsureDate:
    def test_date_input(self):
        d = date(2025, 1, 2)
        assert GarminDailyCache._ensure_date(d) == d

    def test_datetime_input(self):
        dt = datetime(2025, 1, 2, 13, 0, 0)
        assert GarminDailyCache._ensure_date(dt) == date(2025, 1, 2)

    def test_iso_date_str(self):
        assert GarminDailyCache._ensure_date("2025-10-09") == date(2025, 10, 9)

    def test_iso_datetime_str(self):
        assert GarminDailyCache._ensure_date("2025-10-09T12:34:56+00:00") == date(2025, 10, 9)

    def test_invalid_type_raises(self):
        with pytest.raises(ValueError):
            GarminDailyCache._ensure_date(123)  # type: ignore[arg-type]


class TestDayReadWrite:
    def test_day_path_and_write_read(self, cache: GarminDailyCache):
        d = date(2025, 1, 1)
        path = cache.write_day("stats", d, {"x": 1})
        assert path.exists()
        assert cache.has_day("stats", d) is True
        assert cache.read_day("stats", d) == {"x": 1}

    def test_has_day_false_when_missing(self, cache: GarminDailyCache):
        assert cache.has_day("stats", date(2025, 1, 2)) is False

    def test_read_day_none_when_missing_or_expired(self, tmp_path):
        c = GarminDailyCache(tmp_path / "cache", max_age_days=1)
        d = date.today()
        # missing
        assert c.read_day("stats", d) is None
        # present but stale
        p = c.write_day("stats", d, {"y": 2})
        # backdate file mtime by >1 day
        stale = datetime.now() - timedelta(days=2)
        os.utime(p, times=(stale.timestamp(), stale.timestamp()))
        assert c.has_day("stats", d) is False
        assert c.read_day("stats", d) is None


class TestStaticReadWrite:
    def test_static_write_read(self, cache: GarminDailyCache):
        p = cache.write_static("user/profile.json", {"name": "A"})
        assert p.exists()
        assert cache.read_static("user/profile.json") == {"name": "A"}

    def test_static_expired_returns_none(self, tmp_path):
        c = GarminDailyCache(tmp_path / "cache", max_age_days=1)
        p = c.write_static("user/profile.json", {"z": 3})
        stale = datetime.now() - timedelta(days=3)
        os.utime(p, times=(stale.timestamp(), stale.timestamp()))
        assert c.read_static("user/profile.json") is None


class TestLowLevelIO:
    def test__read_json_invalid_returns_none(self, tmp_path):
        f = tmp_path / "bad.json"
        f.write_text("{ not valid json", encoding="utf-8")
        assert GarminDailyCache._read_json(f) is None

    def test__write_json_creates_parents(self, tmp_path):
        f = tmp_path / "nested/dir/out.json"
        GarminDailyCache._write_json(f, {"hello": "world"})
        assert f.exists()
        assert json.loads(f.read_text(encoding="utf-8")) == {"hello": "world"}


class TestDateRange:
    def test__daterange_inclusive(self):
        start = date(2025, 1, 1)
        end = date(2025, 1, 3)
        got = list(GarminDailyCache._daterange(start, end))
        assert got == [date(2025, 1, 1), date(2025, 1, 2), date(2025, 1, 3)]


class TestActivitiesAggregation:
    def test_read_activities_for_days_dedup_by_id(self, tmp_path):
        c = GarminDailyCache(tmp_path / "cache")
        d1 = date(2025, 1, 1)
        d2 = date(2025, 1, 2)

        # Day 1: id=1 and an object without activityId
        c.write_day(
            "activities/day",
            d1,
            [
                {"activityId": 1, "v": "a"},
                {"name": "no-id-1"},  # will be kept (no id -> identity based)
            ],
        )
        # Day 2: duplicate id=1 (should dedupe) and another no-id (distinct instance -> kept)
        c.write_day("activities/day", d2, [{"activityId": 1, "v": "b"}, {"name": "no-id-2"}])

        out = c.read_activities_for_days([d1, d2])
        # Expect: only one id=1 entry (first occurrence kept), plus two no-id entries
        assert len(out) == 3
        assert any(isinstance(x.get("activityId", None), int) and x["activityId"] == 1 for x in out)
        names = [x.get("name") for x in out if "name" in x]
        assert set(names) == {"no-id-1", "no-id-2"}


class TestMergeDayListUnique:
    def test_merge_default_id_key_activityId(self, tmp_path):
        c = GarminDailyCache(tmp_path / "cache")
        d = date(2025, 2, 1)
        # seed
        c.write_day(
            "activities/day",
            d,
            [
                {"activityId": 1, "a": 1},
                {"activityId": 2, "a": 2},
            ],
        )
        # merge: update id=2, add id=3
        path = c.merge_day_list_unique(
            "activities/day",
            d,
            [
                {"activityId": 2, "a": 20},
                {"activityId": 3, "a": 3},
            ],
        )
        merged = GarminDailyCache._read_json(path)
        as_map = {it["activityId"]: it for it in merged}
        assert set(as_map.keys()) == {1, 2, 3}
        assert as_map[2]["a"] == 20

    def test_merge_custom_id_key(self, tmp_path):
        c = GarminDailyCache(tmp_path / "cache")
        d = date(2025, 3, 1)
        c.write_day(
            "custom/day",
            d,
            [
                {"id": "x", "v": 1},
                {"id": "y", "v": 2},
            ],
        )
        path = c.merge_day_list_unique(
            "custom/day",
            d,
            [
                {"id": "y", "v": 22},
                {"id": "z", "v": 3},
            ],
            id_key="id",
        )
        merged = GarminDailyCache._read_json(path)
        as_map = {it["id"]: it for it in merged}
        assert set(as_map.keys()) == {"x", "y", "z"}
        assert as_map["y"]["v"] == 22


class TestExpiryWithInjectedClock:
    def test_expiry_uses_injected_now(self, tmp_path, monkeypatch):
        c = GarminDailyCache(tmp_path / "cache", max_age_days=1)
        d = date(2025, 4, 1)
        p = c.write_day("stats", d, {"k": 1})
        # fake "now" very far in future
        monkeypatch.setattr(c, "_now", lambda: datetime.now() + timedelta(days=10))
        assert c.has_day("stats", d) is False
        assert c.read_day("stats", d) is None
        # Move file to very recent mtime to flip to non-expired
        fresh = datetime.now()
        os.utime(p, times=(fresh.timestamp(), fresh.timestamp()))
        # with the injected far-future, it still should be expired
        assert c.has_day("stats", d) is False
