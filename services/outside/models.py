import logging
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from typing import Optional, List, Callable


@dataclass(frozen=True)
class Event:
    """Immutable representation of an Outside AthleteReg event.

    Mirrors the common fields returned by GraphQL queries such as
    athleticEvent and athleticEventByURL. Category data is retrieved
    on demand via the categories property, which uses an injected provider
    and local caching to avoid repeated network calls.

    Attributes:
        event_id: Unique numeric event identifier.
        name: Display name of the event.
        event_url: Public-facing event page URL.
        static_url: Canonical/static page URL when available.
        vanity_url: Vanity URL (slug or URL) when provided.
        app_type: Owning application type (BIKEREG, RUNREG, TRIREG, SKIREG).
        city: Host city.
        state: State or region abbreviation.
        zip: Postal or ZIP code when available.
        date: Primary start date/time if supplied by the API.
        event_end_date: End date/time for multi-day events.
        open_reg_date: Registration opening date/time.
        close_reg_date: Registration closing date/time.
        is_open: Whether registration is currently open.
        is_highlighted: Whether the event is highlighted/promoted.
        latitude: Latitude in decimal degrees.
        longitude: Longitude in decimal degrees.
        event_types: Raw list of strings describing event types.

    Notes:
        - Instances are frozen (immutable). The categories property uses
          an internal cache updated via object.__setattr__ under a lock.
        - The categories provider is injected by the API client to allow
          lazy resolution without coupling the dataclass to transport code.
    """

    event_id: int
    name: Optional[str]
    event_url: Optional[str]
    static_url: Optional[str]
    vanity_url: Optional[str]
    app_type: Optional[str]
    city: Optional[str]
    state: Optional[str]
    zip: Optional[str]
    date: Optional[datetime]
    event_end_date: Optional[datetime]
    open_reg_date: Optional[datetime]
    close_reg_date: Optional[datetime]
    is_open: Optional[bool]
    is_highlighted: Optional[bool]
    latitude: Optional[float]
    longitude: Optional[float]
    event_types: Optional[List[str]]

    # Lazy categories support (not part of the public constructor surface)
    _categories_provider: Optional[Callable[[int], List["EventCategory"]]] = field(
        default=None, repr=False, compare=False
    )
    _categories_cache: Optional[List["EventCategory"]] = field(
        default=None, repr=False, compare=False
    )
    _categories_lock: Lock = field(default_factory=Lock, repr=False, compare=False)

    @property
    def categories(self) -> List["EventCategory"]:
        """Return the event's categories, resolving them lazily on first access.

        Behavior:
            - If a provider was injected, it is called exactly once (under a lock)
              and the resulting list is cached for subsequent accesses.
            - If no provider is available or an error occurs, an empty list is returned.

        Returns:
            List[EventCategory]: The categories associated with this event.

        Thread safety:
            Resolution and cache population are guarded by an instance-level Lock
            to avoid duplicate fetches in concurrent contexts.
        """
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
    """Metadata describing an event type (from athleticEventTypes).

    Attributes:
        type_id: Numeric identifier of the type.
        description: Human-readable description.
        priority: Optional type priority (higher is typically more prominent).
        filterable_on_calendar: Whether this type can be used to filter calendar results.
        map_key_color: Hex color used on maps for this type, when provided.
        display_status_on_map: Display status text for map overlays, when provided.
    """

    type_id: int
    description: Optional[str]
    priority: Optional[int]
    filterable_on_calendar: bool
    map_key_color: Optional[str]
    display_status_on_map: Optional[str]


@dataclass(frozen=True)
class EventCategory:
    """A single competition/category within an event.

    Examples include a 10K within a running event, a Cat 4 within a cycling event,
    or a Sprint within a triathlon.

    Attributes:
        name: Category name (e.g., "10K", "Cat 4").
        race_rec_id: Provider-specific race record identifier, when present.
        start_time: Scheduled start date/time for this category.
        distance: Display distance value (string as provided).
        distance_unit: Unit for distance (e.g., "mi", "km").
        app_type: Owning application type (BIKEREG, RUNREG, TRIREG, SKIREG).
        event_id: Parent event identifier if supplied with the category.
        race_dates: Dates on which this category takes place.
    """

    name: Optional[str]
    race_rec_id: Optional[str]
    start_time: Optional[datetime]
    distance: Optional[str]
    distance_unit: Optional[str]
    app_type: Optional[str]
    event_id: Optional[int]
    race_dates: List[datetime]


@dataclass(frozen=True)
class SanctioningBody:
    """Organizing or sanctioning body reference (from ARegSanctioningBodies).

    Attributes:
        id: Numeric identifier of the sanctioning body.
        name: Organization name.
        app_type: Owning application type string.
    """

    id: int
    name: Optional[str]
    app_type: str


@dataclass(frozen=True)
class PageInfo:
    """Cursor-based pagination metadata (GraphQL PageInfo).

    Attributes:
        has_next_page: Whether more results exist when paginating forward.
        has_previous_page: Whether more results exist when paginating backward.
        start_cursor: Cursor marking the start of the current page.
        end_cursor: Cursor marking the end of the current page.
    """

    has_next_page: bool
    has_previous_page: bool
    start_cursor: Optional[str]
    end_cursor: Optional[str]


@dataclass(frozen=True)
class CalendarNode:
    """Flattened calendar node representing a calendar search entry.

    Attributes:
        id: GraphQL node identifier.
        event_id: Numeric event identifier.
        app_type: Owning application type (BIKEREG, RUNREG, TRIREG, SKIREG).
        start_date: Start date/time of the entry (may reflect a window).
        end_date: End date/time of the entry.
        open_reg_date: Registration opening date/time for the entry.
        close_reg_date: Registration closing date/time for the entry.
        name: Display name for the entry.
        city: City for the entry or event.
        state: State or region abbreviation.
        latitude: Latitude coordinate if available.
        longitude: Longitude coordinate if available.
        search_entry_type: Entry type indicator from the API.
        is_membership: Membership indicator (integer flag), when present.
        promotion_level: Promotion level indicator, when present.
        event: Flattened AthleticEvent payload if present in the node.
    """

    id: str
    event_id: int
    app_type: str
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    open_reg_date: Optional[datetime]
    close_reg_date: Optional[datetime]
    name: Optional[str]
    city: Optional[str]
    state: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    search_entry_type: Optional[str]
    is_membership: Optional[int]
    promotion_level: Optional[int]
    # Flattened athleticEvent payload (if present)
    event: Optional[Event]


@dataclass(frozen=True)
class CalendarResult:
    """Container for calendar search results.

    Attributes:
        total_count: Total number of results available for the search.
        page_info: Cursor pagination metadata.
        nodes: List of CalendarNode items for the current page.
    """

    total_count: int
    page_info: PageInfo
    nodes: List[CalendarNode]
