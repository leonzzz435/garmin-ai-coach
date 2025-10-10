import logging
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Callable, Union
import json
import httpx

from services.outside.models import (
    Event,
    EventCategory,
    EventType,
    SanctioningBody,
    CalendarResult,
    CalendarNode,
    PageInfo,
)


class OutsideApiGraphQlClient:
    """GraphQL client for Outside AthleteReg event data.

    Wraps the public endpoint at https://outsideapi.com/fed-gw/graphql for the
    four supported application types: BIKEREG, RUNREG, TRIREG, SKIREG. Produces
    typed results defined in services.outside.models, supports cursor pagination,
    and can optionally pre-fetch and cache categories on Event objects.

    Typical usage:
        client = OutsideApiGraphQlClient(app_type="BIKEREG")
        event = client.get_event(12345, precache=True)

    Error handling:
        - Transport errors raise httpx.HTTPError.
        - Non-2xx responses raise httpx.HTTPStatusError with parsed GraphQL errors when available.
        - GraphQL "errors" in a 200 OK response raise RuntimeError.

    Key methods:
      - get_event(event_id, precache=False) -> Optional[Event]
      - get_events(event_ids, batch_size=25, precache=False) -> List[Optional[Event]]
      - get_event_by_url(url, precache=False) -> Optional[Event]
      - get_event_types(type_priorities=None) -> List[EventType]
      - get_sanctioning_bodies() -> List[SanctioningBody]
      - search_calendar(params, first=None, after=None, last=None, before=None, precache=False) -> CalendarResult
      - get_competitions(entries) -> List[Dict[str, Any]]
    """

    _EVENT_BASE_FIELDS = (
        "eventId name eventUrl staticUrl vanityUrl appType city state zip "
        "date eventEndDate openRegDate closeRegDate isOpen isHighlighted "
        "latitude longitude eventTypes"
    )
    _CATEGORIES_FIELDS = (
        "categories { "
        "name raceRecId startTime distance distanceUnit appType eventId raceDates "
        "}"
    )
    _ALLOWED_APP_TYPES = {"BIKEREG", "RUNREG", "TRIREG", "SKIREG"}

    def __init__(
        self,
        app_type: str = "BIKEREG",
        endpoint: str = "https://outsideapi.com/fed-gw/graphql",
        client: Optional[httpx.Client] = None,
        timeout_s: float = 20.0,
        headers: Optional[Dict[str, str]] = None,
    ):
        """Initialize the GraphQL client.

        Args:
            app_type: Application type to scope queries to. Must be one of
                {"BIKEREG", "RUNREG", "TRIREG", "SKIREG"}.
            endpoint: GraphQL endpoint URL.
            client: Optional preconfigured httpx.Client to reuse connections and settings.
            timeout_s: Client timeout in seconds (ignored if a client is provided).
            headers: Optional default headers; "Content-Type" is set automatically by httpx when using json=.

        Raises:
            ValueError: If app_type is not a supported ApplicationType.
        """
        self.app_type = self._normalize_and_validate_app_type(app_type)
        self.endpoint = endpoint
        base_headers = headers or {"User-Agent": "garmin-ai-coach/1.0"}
        # httpx sets Content-Type automatically when using json=...; we keep headers minimal here
        self._client = client or httpx.Client(timeout=timeout_s, headers=base_headers)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info("Initialized OutsideApiGraphQlClient for app_type=%s", self.app_type)

    # ---------------
    # Public Methods
    # ---------------
    def get_event(self, event_id: int, precache: bool = False) -> Optional[Event]:
        """Fetch a single event by numeric identifier.

        When precache is True, category data is included inline (when available)
        and seeded into the Event's lazy categories cache.

        Args:
            event_id: Outside event identifier.
            precache: If True, include categories inline and pre-populate the Event's cache.

        Returns:
            Event if found; otherwise None.

        Raises:
            httpx.HTTPError: On transport failures.
            httpx.HTTPStatusError: On non-2xx HTTP responses (message includes GraphQL errors if present).
            RuntimeError: If GraphQL-level errors are returned with HTTP 200.
        """
        selection = self._EVENT_BASE_FIELDS + (f" {self._CATEGORIES_FIELDS}" if precache else "")
        query = f"""
        query($appType: ApplicationType!, $id: Int!) {{
          athleticEvent(appType: $appType, id: $id) {{
            {selection}
          }}
        }}
        """
        data = self._gql(query, {"appType": self.app_type, "id": int(event_id)})
        node = ((data or {}).get("athleticEvent")) if data else None
        return self._map_event(node, precache_categories=precache)

    def get_event_categories(self, event_id: int) -> List[EventCategory]:
        """Retrieve categories for a given event.

        Fetches EventCategory objects with fields:
        name, raceRecId, startTime, distance, distanceUnit, appType, eventId, raceDates.

        Args:
            event_id: Outside event identifier.

        Returns:
            List[EventCategory]: Zero or more categories for the event.

        Raises:
            httpx.HTTPError: On transport failures.
            httpx.HTTPStatusError: On non-2xx HTTP responses (message includes GraphQL errors if present).
            RuntimeError: If GraphQL-level errors are returned with HTTP 200.
        """
        query = """
            query($appType: ApplicationType!, $id: Int!) {
              athleticEvent(appType: $appType, id: $id) {
                categories {
                  name
                  raceRecId
                  startTime
                  distance
                  distanceUnit
                  appType
                  eventId
                  raceDates
                }
              }
            }
            """
        data = self._gql(query, {"appType": self.app_type, "id": int(event_id)}) or {}
        cats = ((data.get("athleticEvent") or {}).get("categories")) or []
        out: List[EventCategory] = []
        for c in cats:
            if isinstance(c, dict):
                out.append(self._map_category(c))
        return out

    def get_events(
        self, event_ids: List[int], batch_size: int = 25, precache: bool = False
    ) -> List[Optional[Event]]:
        """Fetch multiple events by id using GraphQL aliases, preserving input order.

        The provided IDs are chunked into batches to avoid very large queries. For each
        ID in the input, the aligned result is either an Event or None if not found.

        Args:
            event_ids: List of numeric event identifiers to resolve.
            batch_size: Maximum number of event IDs per GraphQL request.
            precache: If True, include and cache categories for each returned event.

        Returns:
            List[Optional[Event]]: Results aligned to event_ids.

        Raises:
            httpx.HTTPError: On transport failures.
            httpx.HTTPStatusError: On non-2xx HTTP responses (message includes GraphQL errors if present).
            RuntimeError: If GraphQL-level errors are returned with HTTP 200.
        """
        results: List[Optional[Event]] = []
        selection_extra = f" {self._CATEGORIES_FIELDS}" if precache else ""
        for chunk in self._chunks(event_ids, batch_size):
            alias_vars = {}
            var_defs = ["$appType: ApplicationType!"]
            selections = []
            for i, eid in enumerate(chunk):
                var_name = f"id_{i}"
                alias = f"e_{i}"
                var_defs.append(f"${var_name}: Int!")
                selections.append(
                    f"""{alias}: athleticEvent(appType: $appType, id: ${var_name}) {{
                            {self._EVENT_BASE_FIELDS}{selection_extra}
                        }}"""
                )
                alias_vars[var_name] = int(eid)

            query = f"query({', '.join(var_defs)}) {{\n" + "\n".join(selections) + "\n}"
            variables = {"appType": self.app_type, **alias_vars}
            data = self._gql(query, variables) or {}
            # preserve order for this chunk
            for i, _eid in enumerate(chunk):
                node = data.get(f"e_{i}")
                results.append(
                    self._map_event(node, precache_categories=precache) if node else None
                )
        return results

    def get_event_by_url(self, url: str, precache: bool = False) -> Optional[Event]:
        """Fetch a single event by its public URL.

        Args:
            url: Public event URL.
            precache: If True, include categories inline and pre-populate the Event's cache.

        Returns:
            Event if found; otherwise None.

        Raises:
            httpx.HTTPError: On transport failures.
            httpx.HTTPStatusError: On non-2xx HTTP responses (message includes GraphQL errors if present).
            RuntimeError: If GraphQL-level errors are returned with HTTP 200.
        """
        selection = self._EVENT_BASE_FIELDS + (f" {self._CATEGORIES_FIELDS}" if precache else "")
        query = f"""
        query($url: String) {{
          athleticEventByURL(url: $url) {{
            {selection}
          }}
        }}
        """
        data = self._gql(query, {"url": url})
        node = ((data or {}).get("athleticEventByURL")) if data else None
        return self._map_event(node, precache_categories=precache) if node else None

    def get_event_types(self, type_priorities: Optional[List[int]] = None) -> List[EventType]:
        """Return event types for the configured application.

        Args:
            type_priorities: Optional list of priorities used by the API to order/filter results.

        Returns:
            List[EventType]: Event type metadata for the selected app_type.

        Raises:
            httpx.HTTPError: On transport failures.
            httpx.HTTPStatusError: On non-2xx HTTP responses (message includes GraphQL errors if present).
            RuntimeError: If GraphQL-level errors are returned with HTTP 200.
        """
        query = """
        query($appType: ApplicationType!, $typePriorities: [Int!]) {
          athleticEventTypes(appType: $appType, typePriorities: $typePriorities) {
            typeID typeDesc typePriority filterableOnCalendar mapKeyColor displayStatusOnMap
          }
        }
        """
        vars_ = {"appType": self.app_type, "typePriorities": type_priorities}
        data = self._gql(query, vars_) or {}
        items = data.get("athleticEventTypes") or []
        return [self._map_event_type(it) for it in items if isinstance(it, dict)]

    def get_sanctioning_bodies(self) -> List[SanctioningBody]:
        """Return known sanctioning bodies.

        Returns:
            List[SanctioningBody]: Known bodies with id, name, and app_type.

        Raises:
            httpx.HTTPError: On transport failures.
            httpx.HTTPStatusError: On non-2xx HTTP responses (message includes GraphQL errors if present).
            RuntimeError: If GraphQL-level errors are returned with HTTP 200.
        """
        query = """
        query {
          ARegSanctioningBodies {
            id name appType
          }
        }
        """
        data = self._gql(query, {}) or {}
        items = data.get("ARegSanctioningBodies") or []
        out: List[SanctioningBody] = []
        for it in items:
            if not isinstance(it, dict):
                continue
            out.append(
                SanctioningBody(
                    id=int(it["id"]),
                    name=it.get("name"),
                    app_type=str(it.get("appType")),
                )
            )
        return out

    def search_calendar(
        self,
        params: Optional[Dict[str, Any]] = None,
        first: Optional[int] = None,
        after: Optional[str] = None,
        last: Optional[int] = None,
        before: Optional[str] = None,
        precache: bool = False,
    ) -> CalendarResult:
        """Search the event calendar with cursor-based pagination.

        Wraps the athleticEventCalendar query and maps results to CalendarResult.
        When precache is True, nested athleticEvent nodes include categories and
        the corresponding Event objects are pre-cached.

        Args:
            params: A dict matching SearchEventQueryParamsInput (per Outside API).
            first: Page size for forward pagination (mutually exclusive with last).
            after: Cursor token for forward pagination.
            last: Page size for backward pagination (mutually exclusive with first).
            before: Cursor token for backward pagination.
            precache: If True, preload categories on nested Event objects.

        Returns:
            CalendarResult: Total count, page info, and a list of CalendarNode items.

        Raises:
            httpx.HTTPError: On transport failures.
            httpx.HTTPStatusError: On non-2xx HTTP responses (message includes GraphQL errors if present).
            RuntimeError: If GraphQL-level errors are returned with HTTP 200.
        """
        categories_fragment = f" {self._CATEGORIES_FIELDS}" if precache else ""
        query = f"""
        query($searchParameters: SearchEventQueryParamsInput, $first: Int, $after: String, $last: Int, $before: String) {{
          athleticEventCalendar(searchParameters: $searchParameters, first: $first, after: $after, last: $last, before: $before) {{
            totalCount
            pageInfo {{ hasNextPage hasPreviousPage startCursor endCursor }}
            nodes {{
              id eventId appType startDate endDate openRegDate closeRegDate
              name city state latitude longitude searchEntryType isMembership promotionLevel
              athleticEvent {{
                ... on AthleticEvent {{
                  {self._EVENT_BASE_FIELDS}{categories_fragment}
                }}
              }}
            }}
          }}
        }}
        """
        variables = {
            "searchParameters": params or None,
            "first": first,
            "after": after,
            "last": last,
            "before": before,
        }
        data = self._gql(query, variables) or {}
        payload = data.get("athleticEventCalendar") or {}
        page_info = payload.get("pageInfo") or {}
        nodes = payload.get("nodes") or []

        mapped_nodes: List[CalendarNode] = []
        for n in nodes:
            if not isinstance(n, dict):
                continue
            mapped_nodes.append(
                CalendarNode(
                    id=str(n.get("id")),
                    event_id=int(n["eventId"]),
                    app_type=str(n.get("appType")),
                    start_date=self._parse_dt(n.get("startDate")),
                    end_date=self._parse_dt(n.get("endDate")),
                    open_reg_date=self._parse_dt(n.get("openRegDate")),
                    close_reg_date=self._parse_dt(n.get("closeRegDate")),
                    name=n.get("name"),
                    city=n.get("city"),
                    state=n.get("state"),
                    latitude=self._to_float(n.get("latitude")),
                    longitude=self._to_float(n.get("longitude")),
                    search_entry_type=n.get("searchEntryType"),
                    is_membership=n.get("isMembership"),
                    promotion_level=n.get("promotionLevel"),
                    event=self._map_event(
                        (n.get("athleticEvent") or None), precache_categories=precache
                    ),
                )
            )

        return CalendarResult(
            total_count=int(payload.get("totalCount") or 0),
            page_info=PageInfo(
                has_next_page=bool(page_info.get("hasNextPage")),
                has_previous_page=bool(page_info.get("hasPreviousPage")),
                start_cursor=page_info.get("startCursor"),
                end_cursor=page_info.get("endCursor"),
            ),
            nodes=mapped_nodes,
        )

    # ---------------
    # Internals
    # ---------------
    def _map_category(self, node: Dict[str, Any]) -> EventCategory:
        # raceDates are GraphQL Date (often YYYY-MM-DD), startTime may be DateTime
        raw_dates = node.get("raceDates") or []
        race_dates: List[datetime] = []
        for d in raw_dates:
            dt = self._parse_dt(d) or self._parse_dt(f"{d}T00:00:00")
            if dt:
                race_dates.append(dt)

        start_time = self._parse_dt(node.get("startTime"))

        eid = None
        try:
            if node.get("eventId") is not None:
                eid = int(node.get("eventId"))
        except Exception:
            pass

        return EventCategory(
            name=node.get("name"),
            race_rec_id=(node.get("raceRecId") if node.get("raceRecId") is not None else None),
            start_time=start_time,
            distance=node.get("distance"),
            distance_unit=node.get("distanceUnit"),
            app_type=node.get("appType"),
            event_id=eid,
            race_dates=race_dates,
        )

    def _gql(self, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a GraphQL request. On non-2xx responses, attempt to parse and surface
        GraphQL error messages to aid debugging (rather than hiding them behind a 400).
        """
        try:
            resp = self._client.post(self.endpoint, json={"query": query, "variables": variables})
        except httpx.HTTPError as e:
            self.logger.error("GraphQL transport error: %s", e)
            raise

        # Try to parse the JSON body regardless of status; GraphQL servers often include 'errors'
        payload: Dict[str, Any] = {}
        parse_error = None
        try:
            payload = resp.json()
        except Exception as pe:
            parse_error = pe  # keep for logging

        # If 4xx/5xx, raise with as much detail as we can
        if resp.status_code >= 400:
            msg = f"GraphQL HTTP error {resp.status_code}"
            if payload and "errors" in payload:
                try:
                    errs = payload.get("errors") or []
                    # Condense typical GraphQL errors into a single line
                    details = " | ".join(
                        str(e.get("message", "")) for e in errs if isinstance(e, dict)
                    )
                    msg = f"{msg}: {details or json.dumps(errs)[:500]}"
                except Exception:
                    msg = f"{msg}: {json.dumps(payload)[:500]}"
            elif parse_error:
                msg = f"{msg} (also failed to parse JSON errors: {parse_error})"
            self.logger.error(msg)
            # Preserve original semantics too
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                # Attach the parsed errors message for caller visibility
                raise httpx.HTTPStatusError(msg, request=e.request, response=e.response)

        # GraphQL-level errors with 200 OK
        if payload and "errors" in payload and payload["errors"]:
            errs = payload["errors"]
            details = " | ".join(str(e.get("message", "")) for e in errs if isinstance(e, dict))
            self.logger.error("GraphQL errors: %s", details or json.dumps(errs)[:500])
            raise RuntimeError(f"GraphQL errors: {details or json.dumps(errs)[:500]}")

        return payload.get("data") or {}

    @staticmethod
    def _chunks(seq: List[int], size: int) -> Iterable[List[int]]:
        for i in range(0, len(seq), size):
            yield seq[i : i + size]

    @staticmethod
    def _parse_dt(val: Optional[str]) -> Optional[datetime]:
        if not val:
            return None
        # Try common ISO formats
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(val, fmt)
            except ValueError:
                continue
        # Remove timezone colon if present, e.g. +05:00 -> +0500
        if val[-3:-2] == ":":
            vt = val[:-3] + val[-2:]
            try:
                return datetime.strptime(vt, "%Y-%m-%dT%H:%M:%S%z")
            except ValueError:
                return None
        return None

    @staticmethod
    def _to_float(v: Any) -> Optional[float]:
        try:
            return float(v) if v is not None else None
        except Exception:
            return None

    def _map_event(
        self,
        node: Optional[Dict[str, Any]],
        categories_provider: Optional[Callable[[int], List["EventCategory"]]] = None,
        precache_categories: bool = False,
    ) -> Optional[Event]:
        if not isinstance(node, dict):
            return None
        # eventId is a string ID in schema, but the resolver param is Int; coerce safely
        eid_raw = node.get("eventId")
        try:
            eid = int(eid_raw)
        except Exception:
            try:
                eid = int(str(eid_raw))
            except Exception:
                eid = -1

        provider = categories_provider or (lambda event_id: self.get_event_categories(event_id))

        # Optionally pre-cache categories, preferring inline data when present
        preloaded: Optional[List[EventCategory]] = None
        if precache_categories:
            inline = node.get("categories")
            if isinstance(inline, list):
                preloaded = [self._map_category(c) for c in inline if isinstance(c, dict)]
            else:
                try:
                    preloaded = provider(eid)
                except Exception as e:
                    self.logger.exception(
                        "Failed to precache categories for event_id=%s: %s", eid, e
                    )
                    preloaded = []

        return Event(
            event_id=eid,
            name=node.get("name"),
            event_url=node.get("eventUrl"),
            static_url=node.get("staticUrl"),
            vanity_url=node.get("vanityUrl"),
            app_type=node.get("appType"),
            city=node.get("city"),
            state=node.get("state"),
            zip=node.get("zip"),
            date=self._parse_dt(node.get("date")),
            event_end_date=self._parse_dt(node.get("eventEndDate")),
            open_reg_date=self._parse_dt(node.get("openRegDate")),
            close_reg_date=self._parse_dt(node.get("closeRegDate")),
            is_open=node.get("isOpen"),
            is_highlighted=node.get("isHighlighted"),
            latitude=self._to_float(node.get("latitude")),
            longitude=self._to_float(node.get("longitude")),
            event_types=list(node.get("eventTypes") or []),
            _categories_provider=provider,
            _categories_cache=preloaded,
        )

    @staticmethod
    def _map_event_type(node: Dict[str, Any]) -> EventType:
        return EventType(
            type_id=int(node["typeID"]),
            description=node.get("typeDesc"),
            priority=node.get("typePriority"),
            filterable_on_calendar=bool(node.get("filterableOnCalendar")),
            map_key_color=node.get("mapKeyColor"),
            display_status_on_map=node.get("displayStatusOnMap"),
        )

    def _normalize_priority_value(self, p: Any) -> str:
        p_str = str(p or "B").strip().upper()
        return p_str if p_str in {"A", "B", "C"} else "B"

    def get_competitions(
        self, entries: Union[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]
    ) -> List[Dict[str, Any]]:
        """Convert Outside entries to normalized competition dictionaries.

        Supports either:
          - List[dict]: [{"id": 12345, "priority": "A", "target_time": "4:00:00"}]
            Uses this client's app_type for all entries; each item must include "id" or "url".
          - Dict[str, List[dict]]: {"bikereg": [...], "runreg": [...], "trireg": [...], "skireg": [...]}
            Dispatches automatically per section using sub-clients that reuse this client's HTTPX session.

        Normalization:
            - date: ISO YYYY-MM-DD (prefers event.date, then earliest category race date, then event_end_date)
            - race_type: First category name if available; else first event type; else "AthleteReg Event"
            - priority: Normalized to one of {"A", "B", "C"} (defaults to "B")
            - target_time: Taken verbatim if supplied
            - location: "City, State" if available

        Args:
            entries: Either a list of entry dictionaries or a mapping of app sections to lists of entries.

        Returns:
            List[Dict[str, Any]]: Normalized competition dictionaries suitable for downstream planning.

        Side effects:
            Logs warnings for invalid entries or missing events and logs errors for retrieval failures.
        """
        # Dispatch if we received a mapping {bikereg|runreg|trireg|skireg: [...]}
        if isinstance(entries, dict):
            out: List[Dict[str, Any]] = []
            app_map = {
                "bikereg": "BIKEREG",
                "runreg": "RUNREG",
                "trireg": "TRIREG",
                "skireg": "SKIREG",
            }
            for key, lst in entries.items():
                if not lst:
                    continue
                app_type = app_map.get(str(key).strip().lower())
                if not app_type:
                    self.logger.warning("Unknown Outside app section '%s' ignored", key)
                    continue
                try:
                    # Reuse the same HTTPX session/endpoint
                    sub = OutsideApiGraphQlClient(
                        app_type=app_type,
                        endpoint=self.endpoint,
                        client=self._client,
                    )
                    out.extend(sub.get_competitions(lst))  # recurse into list handler below
                except Exception as e:
                    self.logger.error("Failed resolving competitions for '%s': %s", key, e)
            return out

        # --- Existing list handler (unchanged logic) ---
        if not isinstance(entries, list) or not entries:
            return []

        from datetime import datetime, date as _date

        def _iso_date(d: Any) -> str | None:
            try:
                if isinstance(d, datetime):
                    return d.date().isoformat()
                if isinstance(d, _date):
                    return d.isoformat()
                if isinstance(d, str) and d:
                    return d.split("T")[0]
            except Exception:
                return None
            return None

        resolved: List[Dict[str, Any]] = []

        for entry in entries:
            eid = entry.get("id")
            url = entry.get("url")

            if not eid and not url:
                self.logger.warning("outside entry requires 'id' or 'url': %s", entry)
                continue

            event = None
            try:
                if eid:
                    event = self.get_event(int(eid), precache=True)
                elif url:
                    event = self.get_event_by_url(url, precache=True)
            except Exception as e:
                self.logger.error(
                    "Failed to retrieve event (%s): %s", f"id={eid}" if eid else f"url={url}", e
                )
                event = None

            if not event:
                self.logger.warning(
                    "OutsideAPI event not found (%s)", f"id={eid}" if eid else f"url={url}"
                )
                continue

            # Event date: prefer event.date, else earliest category race date, else event_end_date
            event_date = event.date
            if event_date is None:
                earliest = None
                try:
                    cats = event.categories
                except Exception:
                    cats = []
                for c in cats or []:
                    for rd in c.race_dates or []:
                        if earliest is None or (rd and rd < earliest):
                            earliest = rd
                event_date = earliest or event.event_end_date

            iso_date = _iso_date(event_date)
            if not iso_date:
                self.logger.warning(
                    "OutsideAPI event missing usable date; skipping (%s)",
                    f"id={eid}" if eid else f"url={url}",
                )
                continue

            # race_type: prefer first category name; else first event_types entry; else generic
            race_type = None
            try:
                cats = event.categories
            except Exception:
                cats = []
            if cats:
                for c in cats:
                    if getattr(c, "name", None):
                        race_type = c.name
                        break
            if not race_type:
                et = event.event_types or []
                race_type = et[0] if et else "AthleteReg Event"

            location = ", ".join([x for x in [event.city, event.state] if x]) or None

            comp: Dict[str, Any] = {
                "name": event.name or (f"Outside Event {eid}" if eid else "Outside Event"),
                "date": iso_date,
                "race_type": race_type,
                "priority": self._normalize_priority_value(entry.get("priority")),
                "target_time": entry.get("target_time", ""),
            }
            if location:
                comp["location"] = location

            resolved.append(comp)
            self.logger.info("Added OutsideAPI competition: %s on %s", comp["name"], comp["date"])

        if resolved:
            self.logger.info("OutsideAPI: resolved %d competitions", len(resolved))
        else:
            self.logger.info("OutsideAPI: no competitions resolved")
        return resolved

    def _normalize_and_validate_app_type(self, app_type: str) -> str:
        at = (app_type or "").strip().upper()
        if at not in self._ALLOWED_APP_TYPES:
            raise ValueError(
                f"Invalid app_type '{app_type}'. Must be one of {self._ALLOWED_APP_TYPES}. "
                "See Outside AthleteReg GraphQL ApplicationType enum."
            )
        return at
