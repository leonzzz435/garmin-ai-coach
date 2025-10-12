import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock


@dataclass(frozen=True)
class Event:
    event_id: int
    name: str | None
    event_url: str | None
    static_url: str | None
    vanity_url: str | None
    app_type: str | None
    city: str | None
    state: str | None
    zip: str | None
    date: datetime | None
    event_end_date: datetime | None
    open_reg_date: datetime | None
    close_reg_date: datetime | None
    is_open: bool | None
    is_highlighted: bool | None
    latitude: float | None
    longitude: float | None
    event_types: list[str] | None

    _categories_provider: Callable[[int], list["EventCategory"]] | None = field(
        default=None, repr=False, compare=False
    )
    _categories_cache: list["EventCategory"] | None = field(default=None, repr=False, compare=False)
    _categories_lock: Lock = field(default_factory=Lock, repr=False, compare=False)

    @property
    def categories(self) -> list["EventCategory"]:
        cached = self._categories_cache
        if cached is not None:
            return cached

        provider = self._categories_provider
        if provider is None:
            return []

        with self._categories_lock:
            cached = self._categories_cache
            if cached is not None:
                return cached
            try:
                cats = provider(self.event_id) or []
            except Exception as e:
                logging.getLogger(
                    f"{self.__class__.__module__}.{self.__class__.__name__}"
                ).exception("Failed to load categories for event_id=%s: %s", self.event_id, e)
                cats = []
            object.__setattr__(self, "_categories_cache", cats)
            return cats


@dataclass(frozen=True)
class EventType:
    type_id: int
    description: str | None
    priority: int | None
    filterable_on_calendar: bool
    map_key_color: str | None
    display_status_on_map: str | None


@dataclass(frozen=True)
class EventCategory:
    name: str | None
    race_rec_id: str | None
    start_time: datetime | None
    distance: str | None
    distance_unit: str | None
    app_type: str | None
    event_id: int | None
    race_dates: list[datetime]


@dataclass(frozen=True)
class SanctioningBody:
    id: int
    name: str | None
    app_type: str


@dataclass(frozen=True)
class PageInfo:
    has_next_page: bool
    has_previous_page: bool
    start_cursor: str | None
    end_cursor: str | None


@dataclass(frozen=True)
class CalendarNode:
    id: str
    event_id: int
    app_type: str
    start_date: datetime | None
    end_date: datetime | None
    open_reg_date: datetime | None
    close_reg_date: datetime | None
    name: str | None
    city: str | None
    state: str | None
    latitude: float | None
    longitude: float | None
    search_entry_type: str | None
    is_membership: int | None
    promotion_level: int | None
    event: Event | None


@dataclass(frozen=True)
class CalendarResult:
    total_count: int
    page_info: PageInfo
    nodes: list[CalendarNode]
