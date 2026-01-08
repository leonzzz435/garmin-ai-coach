import json
import logging
from collections.abc import Callable, Iterable
from datetime import datetime
from typing import Any

import httpx

from services.outside.models import (
    CalendarNode,
    CalendarResult,
    Event,
    EventCategory,
    EventType,
    PageInfo,
    SanctioningBody,
)


class OutsideApiGraphQlClient:
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
        client: httpx.Client | None = None,
        timeout_s: float = 20.0,
        headers: dict[str, str] | None = None,
    ):
        self.app_type = self._normalize_and_validate_app_type(app_type)
        self.endpoint = endpoint
        base_headers = headers or {"User-Agent": "garmin-ai-coach/1.0"}
        self._client = client or httpx.Client(timeout=timeout_s, headers=base_headers)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.debug("Initialized OutsideApiGraphQlClient for app_type=%s", self.app_type)

    def get_event(self, event_id: int, precache: bool = False) -> Event | None:
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

    def get_event_categories(self, event_id: int) -> list[EventCategory]:
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
        out: list[EventCategory] = []
        for c in cats:
            if isinstance(c, dict):
                out.append(self._map_category(c))
        return out

    def get_events(
        self, event_ids: list[int], batch_size: int = 25, precache: bool = False
    ) -> list[Event | None]:
        results: list[Event | None] = []
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

            for i, _eid in enumerate(chunk):
                node = data.get(f"e_{i}")
                results.append(
                    self._map_event(node, precache_categories=precache) if node else None
                )
        return results

    def get_event_by_url(self, url: str, precache: bool = False) -> Event | None:
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

    def get_event_types(self, type_priorities: list[int] | None = None) -> list[EventType]:
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

    def get_sanctioning_bodies(self) -> list[SanctioningBody]:
        query = """
        query {
          ARegSanctioningBodies {
            id name appType
          }
        }
        """
        data = self._gql(query, {}) or {}
        items = data.get("ARegSanctioningBodies") or []
        out: list[SanctioningBody] = []
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
        params: dict[str, Any] | None = None,
        first: int | None = None,
        after: str | None = None,
        last: int | None = None,
        before: str | None = None,
        precache: bool = False,
    ) -> CalendarResult:
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

        mapped_nodes: list[CalendarNode] = []
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

    def _map_category(self, node: dict[str, Any]) -> EventCategory:
        raw_dates = node.get("raceDates") or []
        race_dates: list[datetime] = []
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

    def _gql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        try:
            resp = self._client.post(self.endpoint, json={"query": query, "variables": variables})
        except httpx.HTTPError as e:
            self.logger.error("GraphQL transport error: %s", e)
            raise

        payload: dict[str, Any] = {}
        parse_error = None
        try:
            payload = resp.json()
        except Exception as pe:
            parse_error = pe

        if resp.status_code >= 400:
            msg = f"GraphQL HTTP error {resp.status_code}"
            if payload and "errors" in payload:
                try:
                    errs = payload.get("errors") or []
                    details = " | ".join(
                        str(e.get("message", "")) for e in errs if isinstance(e, dict)
                    )
                    msg = f"{msg}: {details or json.dumps(errs)[:500]}"
                except Exception:
                    msg = f"{msg}: {json.dumps(payload)[:500]}"
            elif parse_error:
                msg = f"{msg} (also failed to parse JSON errors: {parse_error})"
            self.logger.error(msg)
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise httpx.HTTPStatusError(msg, request=e.request, response=e.response) from e

        if payload and "errors" in payload and payload["errors"]:
            errs = payload["errors"]
            details = " | ".join(str(e.get("message", "")) for e in errs if isinstance(e, dict))
            self.logger.error("GraphQL errors: %s", details or json.dumps(errs)[:500])
            raise RuntimeError(f"GraphQL errors: {details or json.dumps(errs)[:500]}")

        return payload.get("data") or {}

    @staticmethod
    def _chunks(seq: list[int], size: int) -> Iterable[list[int]]:
        for i in range(0, len(seq), size):
            yield seq[i : i + size]

    @staticmethod
    def _parse_dt(val: str | None) -> datetime | None:
        if not val:
            return None
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(val, fmt)
            except ValueError:
                continue
        if val[-3:-2] == ":":
            vt = val[:-3] + val[-2:]
            try:
                return datetime.strptime(vt, "%Y-%m-%dT%H:%M:%S%z")
            except ValueError:
                return None
        return None

    @staticmethod
    def _to_float(v: Any) -> float | None:
        try:
            return float(v) if v is not None else None
        except Exception:
            return None

    def _map_event(
        self,
        node: dict[str, Any] | None,
        categories_provider: Callable[[int], list["EventCategory"]] | None = None,
        precache_categories: bool = False,
    ) -> Event | None:
        if not isinstance(node, dict):
            return None
        eid_raw = node.get("eventId")
        try:
            eid = int(eid_raw)
        except Exception:
            try:
                eid = int(str(eid_raw))
            except Exception:
                eid = -1

        provider = categories_provider or (lambda event_id: self.get_event_categories(event_id))

        preloaded: list[EventCategory] | None = None
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
    def _map_event_type(node: dict[str, Any]) -> EventType:
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
        self, entries: list[dict[str, Any]] | dict[str, list[dict[str, Any]]]
    ) -> list[dict[str, Any]]:
        if isinstance(entries, dict):
            out: list[dict[str, Any]] = []
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
                    sub = OutsideApiGraphQlClient(
                        app_type=app_type,
                        endpoint=self.endpoint,
                        client=self._client,
                    )
                    out.extend(sub.get_competitions(lst))
                except Exception as e:
                    self.logger.error("Failed resolving competitions for '%s': %s", key, e)
            return out

        if not isinstance(entries, list) or not entries:
            return []

        from datetime import date as _date
        from datetime import datetime

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

        resolved: list[dict[str, Any]] = []

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

            comp: dict[str, Any] = {
                "name": event.name or (f"Outside Event {eid}" if eid else "Outside Event"),
                "date": iso_date,
                "race_type": race_type,
                "priority": self._normalize_priority_value(entry.get("priority")),
                "target_time": entry.get("target_time", ""),
            }
            if location:
                comp["location"] = location

            resolved.append(comp)
            self.logger.debug("Added OutsideAPI competition: %s on %s", comp["name"], comp["date"])

        if resolved:
            self.logger.debug("OutsideAPI: resolved %d competitions", len(resolved))
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
