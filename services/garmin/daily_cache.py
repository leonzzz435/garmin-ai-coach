from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


@dataclass
class GarminDailyCache:
    root: Path
    max_age_days: int | None = None

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _now(self) -> datetime:
        return datetime.now()

    def _expired(self, p: Path) -> bool:
        if not p.exists():
            return True
        if self.max_age_days is None:
            return False
        try:
            stat = p.stat()
        except FileNotFoundError:
            return True
        file_time = datetime.fromtimestamp(stat.st_mtime)
        return (self._now() - file_time) > timedelta(days=self.max_age_days)

    @staticmethod
    def _ensure_date(val: Any) -> date:
        if isinstance(val, date) and not isinstance(val, datetime):
            return val
        if isinstance(val, datetime):
            return val.date()
        if isinstance(val, str):
            try:
                d_part = val.split("T", 1)[0]
                return date.fromisoformat(d_part)
            except Exception as e:
                raise ValueError(f"Invalid ISO date/datetime string: {val}") from e
        raise ValueError(f"Unsupported type for _ensure_date: {type(val).__name__}")

    @staticmethod
    def _daterange(start: date, end: date) -> Iterable[date]:
        cur = start
        while cur <= end:
            yield cur
            cur += timedelta(days=1)

    @staticmethod
    def _read_json(p: Path) -> Any | None:
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None

    @staticmethod
    def _write_json(p: Path, data: Any) -> Path:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return p

    def static_path(self, rel: str) -> Path:
        return self.root / rel

    def write_static(self, rel: str, data: Any) -> Path:
        return self._write_json(self.static_path(rel), data)

    def read_static(self, rel: str) -> Any | None:
        p = self.static_path(rel)
        if not p.exists() or self._expired(p):
            return None
        return self._read_json(p)

    def _day_path(self, category: str, d: date) -> Path:
        return self.static_path(f"{category}/{d.isoformat()}.json")

    def write_day(self, category: str, d: date, data: Any) -> Path:
        return self._write_json(self._day_path(category, d), data)

    def has_day(self, category: str, d: date) -> bool:
        p = self._day_path(category, d)
        return p.exists() and not self._expired(p)

    def read_day(self, category: str, d: date) -> Any | None:
        p = self._day_path(category, d)
        if not p.exists() or self._expired(p):
            return None
        return self._read_json(p)

    def read_activities_for_days(self, days: list[date]) -> list[dict]:
        out: list[dict] = []
        seen_ids: set[Any] = set()
        for d in days:
            day_data = self.read_day("activities/day", d) or []
            if not isinstance(day_data, list):
                continue
            for item in day_data:
                if not isinstance(item, dict):
                    continue
                if "activityId" in item:
                    aid = item.get("activityId")
                    if aid in seen_ids:
                        continue
                    seen_ids.add(aid)
                    out.append(item)
                else:
                    out.append(item)
        return out

    def merge_day_list_unique(
        self, category: str, d: date, items: list[dict], id_key: str = "activityId"
    ) -> Path:
        p = self._day_path(category, d)
        existing: list[dict] = []
        if p.exists():
            data = self._read_json(p)
            if isinstance(data, list):
                existing = data

        keyed: dict[Any, dict] = {}
        no_id: list[dict] = []
        for it in existing:
            if isinstance(it, dict) and id_key in it:
                keyed[it[id_key]] = it
            elif isinstance(it, dict):
                no_id.append(it)

        for it in items:
            if not isinstance(it, dict):
                continue
            if id_key in it:
                keyed[it[id_key]] = it
            else:
                no_id.append(it)

        merged = list(keyed.values()) + no_id
        return self._write_json(p, merged)
