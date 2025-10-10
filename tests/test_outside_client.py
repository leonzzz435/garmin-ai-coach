import json
from datetime import datetime as dt
from typing import Any, Dict, List

import httpx
import pytest

from services.outside.client import OutsideApiGraphQlClient
from services.outside.models import (
    Event,
    EventCategory,
    EventType,
    SanctioningBody,
    CalendarResult,
    CalendarNode,
    PageInfo,
)


@pytest.mark.unit
class TestOutsideApiGraphQlClient:
    # ---------------------------
    # Helpers (class-local)
    # ---------------------------
    @staticmethod
    def _make_event(
        event_id: int = 71252,
        name: str = "Sample Event",
        date: dt | None = dt(2026, 4, 11),
        event_end_date: dt | None = dt(2026, 4, 11),
        city: str | None = "Carlton",
        state: str | None = "OR",
        event_types: list[str] | None = None,
        categories: list[EventCategory] | None = None,
    ) -> Event:
        return Event(
            event_id=event_id,
            name=name,
            event_url=f"https://example.com/events/{event_id}",
            static_url=f"https://static.example.com/events/{event_id}",
            vanity_url=f"vanity-{event_id}",
            app_type="BIKEREG",
            city=city,
            state=state,
            zip="97111",
            date=date,
            event_end_date=event_end_date,
            open_reg_date=dt(2025, 1, 1),
            close_reg_date=dt(2025, 12, 31),
            is_open=True,
            is_highlighted=False,
            latitude=45.2,
            longitude=-123.2,
            event_types=event_types or ["Gravel"],
            _categories_cache=categories or [],
        )

    @staticmethod
    def _make_category(name: str, dts: list[dt]) -> EventCategory:
        return EventCategory(
            name=name,
            race_rec_id="C-1",
            start_time=dts[0] if dts else None,
            distance="100",
            distance_unit="miles",
            app_type="BIKEREG",
            event_id=999,
            race_dates=dts,
        )

    @staticmethod
    def _make_httpx_response(
        status: int, url: str, payload: Dict[str, Any] | None = None, content: bytes | None = None
    ):
        request = httpx.Request("POST", url)
        if payload is not None:
            content = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"} if payload is not None else {}
        return httpx.Response(status, request=request, content=content or b"", headers=headers)

    # ---------------------------
    # Existing tests (kept) + merges
    # ---------------------------
    def test_init_default_and_validation(self):
        # Default should normalize to BIKEREG
        c = OutsideApiGraphQlClient()
        assert c.app_type == "BIKEREG"

        # Case-insensitive valid app types normalize to upper
        c2 = OutsideApiGraphQlClient(app_type="runreg")
        assert c2.app_type == "RUNREG"

        # Invalid should raise
        with pytest.raises(ValueError):
            OutsideApiGraphQlClient(app_type="OUTSIDE_API")

    def test__gql_200_with_graphql_errors_raises_runtimeerror(self, monkeypatch):
        client = OutsideApiGraphQlClient()

        def fake_post(url: str, json: Dict[str, Any]):
            request = httpx.Request("POST", url)
            payload = {"errors": [{"message": "Something went wrong"}]}
            return httpx.Response(
                200, request=request, content=jsonlib.dumps(payload).encode("utf-8")
            )

        # Use stdlib json in closure
        jsonlib = json
        monkeypatch.setattr(client._client, "post", fake_post)

        with pytest.raises(RuntimeError) as exc:
            client._gql("query Q { x }", {})
        assert "Something went wrong" in str(exc.value)

    def test__gql_400_with_errors_raises_httpstatusexterror(self, monkeypatch):
        client = OutsideApiGraphQlClient()

        def fake_post(url: str, json: Dict[str, Any]):
            request = httpx.Request("POST", url)
            payload = {"errors": [{"message": "Bad variable for appType"}]}
            return httpx.Response(
                400, request=request, content=jsonlib.dumps(payload).encode("utf-8")
            )

        jsonlib = json
        monkeypatch.setattr(client._client, "post", fake_post)

        with pytest.raises(httpx.HTTPStatusError) as exc:
            client._gql("query Q { x }", {})
        # Our custom raiser includes this prefix
        assert "GraphQL HTTP error 400" in str(exc.value)
        assert "Bad variable for appType" in str(exc.value)

    def test_get_event_mapping_via__gql(self, monkeypatch):
        client = OutsideApiGraphQlClient()

        # Build a realistic payload per the Outside GraphQL docs
        payload = {
            "eventId": 71252,
            "name": "Sunflower Gravel",
            "eventUrl": "https://www.bikereg.com/sunflower-gravel",
            "staticUrl": "https://www.bikereg.com/sunflower-gravel",
            "vanityUrl": "sunflower-gravel",
            "appType": "BIKEREG",
            "city": "Lawrence",
            "state": "KS",
            "zip": "66044",
            "date": "2026-04-11T00:00:00",
            "eventEndDate": "2026-04-11T23:59:59",
            "openRegDate": "2026-01-01T00:00:00",
            "closeRegDate": "2026-04-10T23:59:59",
            "isOpen": True,
            "isHighlighted": False,
            "latitude": 38.9717,
            "longitude": -95.2353,
            "eventTypes": ["Gravel"],
            "categories": [
                {
                    "name": "100k",
                    "raceRecId": "cat-100",
                    "startTime": "2026-04-11T08:00:00",
                    "distance": "100",
                    "distanceUnit": "miles",
                    "appType": "BIKEREG",
                    "eventId": 71252,
                    "raceDates": ["2026-04-11"],
                }
            ],
        }

        def fake_gql(query: str, variables: Dict[str, Any]):
            assert "athleticEvent" in query
            return {"athleticEvent": payload}

        monkeypatch.setattr(client, "_gql", fake_gql)

        ev = client.get_event(71252, precache=True)
        assert isinstance(ev, Event)
        assert ev.event_id == 71252
        assert ev.name == "Sunflower Gravel"
        assert ev.city == "Lawrence"
        assert ev.state == "KS"
        # categories should be pre-cached and accessible
        cats = ev.categories
        assert isinstance(cats, list) and len(cats) == 1
        assert isinstance(cats[0], EventCategory)
        assert cats[0].name == "100k"

    def test_get_competitions_list_by_id_and_url(self, monkeypatch):
        # Build two fake events: one fetched by id with date fallback via categories,
        # and one fetched by url with direct event date and no categories.
        def build_event_by_id():
            # No event.date; categories earliest date should be used
            return Event(
                event_id=1,
                name="Bike Event By ID",
                event_url="https://www.bikereg.com/id-1",
                static_url="https://www.bikereg.com/id-1",
                vanity_url="id-1",
                app_type="BIKEREG",
                city="Boulder",
                state="CO",
                zip="80301",
                date=None,
                event_end_date=dt(2026, 5, 10, 0, 0, 0),
                open_reg_date=None,
                close_reg_date=None,
                is_open=True,
                is_highlighted=False,
                latitude=40.0,
                longitude=-105.0,
                event_types=["Gravel"],
                _categories_cache=[
                    EventCategory(
                        name="Gravel 100",
                        race_rec_id="r1",
                        start_time=dt(2026, 5, 9, 8, 0, 0),
                        distance="100",
                        distance_unit="miles",
                        app_type="BIKEREG",
                        event_id=1,
                        race_dates=[dt(2026, 5, 9, 0, 0, 0)],
                    )
                ],
            )

        def build_event_by_url():
            # Has event.date and no categories; event.date should be used
            return Event(
                event_id=2,
                name="Run Event By URL",
                event_url="https://www.runreg.com/abc",
                static_url="https://www.runreg.com/abc",
                vanity_url="abc",
                app_type="RUNREG",
                city="Boston",
                state="MA",
                zip="02108",
                date=dt(2026, 6, 1, 0, 0, 0),
                event_end_date=dt(2026, 6, 1, 23, 59, 59),
                open_reg_date=None,
                close_reg_date=None,
                is_open=True,
                is_highlighted=False,
                latitude=42.36,
                longitude=-71.06,
                event_types=["Half Marathon"],
                _categories_cache=[],
            )

        client = OutsideApiGraphQlClient()

        def fake_get_event(eid: int, precache: bool = False):
            assert precache is True
            return build_event_by_id()

        def fake_get_event_by_url(url: str, precache: bool = False):
            assert precache is True
            return build_event_by_url()

        monkeypatch.setattr(client, "get_event", fake_get_event)
        monkeypatch.setattr(client, "get_event_by_url", fake_get_event_by_url)

        entries = [
            {"id": 1, "priority": "A", "target_time": "3:00:00"},
            {"url": "https://www.runreg.com/abc"},  # priority defaults to B
        ]
        comps = client.get_competitions(entries)

        assert len(comps) == 2

        # First: ID-based; date from categories; race_type from first category
        c0 = comps[0]
        assert c0["name"] == "Bike Event By ID"
        assert c0["date"] == "2026-05-09"
        assert c0["race_type"] == "Gravel 100"
        assert c0["priority"] == "A"
        assert c0["target_time"] == "3:00:00"
        assert c0.get("location") == "Boulder, CO"

        # Second: URL-based; date from event.date; race_type from event_types
        c1 = comps[1]
        assert c1["name"] == "Run Event By URL"
        assert c1["date"] == "2026-06-01"
        assert c1["race_type"] == "Half Marathon"
        assert c1["priority"] == "B"  # defaulted
        assert c1.get("location") == "Boston, MA"

    def test_get_competitions_dispatch_dict_sections(self, monkeypatch):
        # Monkeypatch class methods so that behavior depends on self.app_type
        def fake_get_event(self, eid: int, precache: bool = False):
            # Name encodes which section handled the request
            return Event(
                event_id=eid,
                name=f"{self.app_type}-ID-{eid}",
                event_url="x",
                static_url="x",
                vanity_url="x",
                app_type=self.app_type,
                city=None,
                state=None,
                zip=None,
                date=dt(2026, 7, 1, 0, 0, 0),
                event_end_date=dt(2026, 7, 1, 0, 0, 0),
                open_reg_date=None,
                close_reg_date=None,
                is_open=True,
                is_highlighted=False,
                latitude=None,
                longitude=None,
                event_types=["TypeA"],
                _categories_cache=[],
            )

        def fake_get_event_by_url(self, url: str, precache: bool = False):
            return Event(
                event_id=99,
                name=f"{self.app_type}-URL",
                event_url=url,
                static_url=url,
                vanity_url="x",
                app_type=self.app_type,
                city=None,
                state=None,
                zip=None,
                date=dt(2026, 8, 1, 0, 0, 0),
                event_end_date=dt(2026, 8, 1, 0, 0, 0),
                open_reg_date=None,
                close_reg_date=None,
                is_open=True,
                is_highlighted=False,
                latitude=None,
                longitude=None,
                event_types=["TypeB"],
                _categories_cache=[],
            )

        # Patch bound methods on the class so newly-constructed subclients use them
        monkeypatch.setattr(OutsideApiGraphQlClient, "get_event", fake_get_event, raising=True)
        monkeypatch.setattr(
            OutsideApiGraphQlClient, "get_event_by_url", fake_get_event_by_url, raising=True
        )

        root = OutsideApiGraphQlClient()
        config_map = {
            "bikereg": [{"id": 1}],
            "runreg": [{"url": "https://www.runreg.com/foo"}],
            "unknown": [{"id": 123}],  # should be ignored gracefully
        }

        comps = root.get_competitions(config_map)
        # Expect two competitions (bikereg + runreg)
        assert len(comps) == 2
        names = sorted([c["name"] for c in comps])
        assert names == ["BIKEREG-ID-1", "RUNREG-URL"]

    def test_get_competitions_unknown_section_ignored(self, monkeypatch):
        client = OutsideApiGraphQlClient()
        comps = client.get_competitions({"unknown": [{"id": 1}]})
        assert comps == []

    # ---------------------------
    # Added tests (merged)
    # ---------------------------

    @pytest.mark.parametrize(
        "val,expect_none",
        [
            (None, True),
            ("", True),
            ("2026-04-11", False),
            ("2026-04-11T09:10:11", False),
            ("2026-04-11T09:10:11+05:30", False),
            ("not-a-date", True),
        ],
    )
    def test__parse_dt_variants(self, val, expect_none):
        c = OutsideApiGraphQlClient()
        out = c._parse_dt(val)
        assert (out is None) == expect_none
        if out is not None:
            assert isinstance(out, dt)

    @pytest.mark.parametrize(
        "inp,expected",
        [
            (None, None),
            ("3.14", 3.14),
            (42, 42.0),
            ("bad", None),
        ],
    )
    def test__to_float_variants(self, inp, expected):
        c = OutsideApiGraphQlClient()
        assert c._to_float(inp) == expected

    def test__chunks_basic(self):
        c = OutsideApiGraphQlClient()
        seq = list(range(7))
        chunks = list(c._chunks(seq, 3))
        assert chunks == [[0, 1, 2], [3, 4, 5], [6]]

    def test__map_category_parses_dates_and_starttime(self):
        c = OutsideApiGraphQlClient()
        node = {
            "name": "Marathon",
            "raceRecId": "R1",
            "startTime": "2026-02-01T08:00:00",
            "distance": "26.2",
            "distanceUnit": "miles",
            "appType": "RUNREG",
            "eventId": 123,
            "raceDates": ["2026-02-01", "2026-02-02T09:30:00"],
        }
        cat = c._map_category(node)
        assert cat.name == "Marathon"
        assert cat.event_id == 123
        assert len(cat.race_dates) == 2
        assert cat.start_time is not None

    def test__map_event_inline_categories_precache(self):
        c = OutsideApiGraphQlClient()
        node = {
            "eventId": "555",
            "name": "InlineCats",
            "eventUrl": "u",
            "staticUrl": "s",
            "vanityUrl": "v",
            "appType": "BIKEREG",
            "city": "X",
            "state": "Y",
            "zip": "00000",
            "date": "2026-01-01",
            "eventEndDate": "2026-01-02",
            "openRegDate": "2025-01-01",
            "closeRegDate": "2025-06-01",
            "isOpen": True,
            "isHighlighted": False,
            "latitude": 0.0,
            "longitude": 0.0,
            "eventTypes": [],
            "categories": [
                {
                    "name": "Cat A",
                    "raceRecId": "RA",
                    "startTime": "2026-01-01T08:00:00",
                    "distance": "40",
                    "distanceUnit": "km",
                    "appType": "BIKEREG",
                    "eventId": 555,
                    "raceDates": ["2026-01-01"],
                }
            ],
        }
        ev = c._map_event(node, precache_categories=True)
        assert isinstance(ev, Event)
        assert ev.event_id == 555
        assert len(ev.categories) == 1
        assert ev.categories[0].name == "Cat A"

    def test__map_event_provider_precache_and_provider_error(self, caplog):
        c = OutsideApiGraphQlClient()
        node = {
            "eventId": "556",
            "name": "ProviderCats",
            "eventUrl": "u",
            "staticUrl": "s",
            "vanityUrl": "v",
            "appType": "BIKEREG",
            "city": "X",
            "state": "Y",
            "zip": "00000",
            "date": "2026-01-01",
            "eventEndDate": "2026-01-02",
            "openRegDate": "2025-01-01",
            "closeRegDate": "2025-06-01",
            "isOpen": True,
            "isHighlighted": False,
            "latitude": 0.0,
            "longitude": 0.0,
            "eventTypes": [],
        }

        def bad_provider(_eid: int) -> List[EventCategory]:
            raise RuntimeError("boom")

        ev = c._map_event(node, categories_provider=bad_provider, precache_categories=True)
        assert isinstance(ev, Event)
        assert ev.event_id == 556
        assert ev.categories == []
        assert any("Failed to precache categories" in line for line in caplog.text.splitlines())

    def test__map_event_no_dict_returns_none(self):
        c = OutsideApiGraphQlClient()
        assert c._map_event(None) is None

    def test__map_event_type_mapping(self):
        c = OutsideApiGraphQlClient()
        node = {
            "typeID": "7",
            "typeDesc": "Gravel",
            "typePriority": 10,
            "filterableOnCalendar": True,
            "mapKeyColor": "#00FF00",
            "displayStatusOnMap": "SHOW_ON_MAP",
        }
        et = c._map_event_type(node)
        assert isinstance(et, EventType)
        assert et.type_id == 7
        assert et.description == "Gravel"
        assert et.filterable_on_calendar is True

    def test__gql_http_500_parse_error(self, monkeypatch):
        c = OutsideApiGraphQlClient()
        resp = self._make_httpx_response(
            500, c.endpoint, payload=None, content=b"<html>oops</html>"
        )
        monkeypatch.setattr(c._client, "post", lambda url, json: resp)
        with pytest.raises(httpx.HTTPStatusError) as ei:
            c._gql("query { y }", {})
        msg = str(ei.value)
        assert "GraphQL HTTP error 500" in msg
        assert "failed to parse JSON errors" in msg

    def test__gql_200_success_returns_data(self, monkeypatch):
        c = OutsideApiGraphQlClient()
        payload = {"data": {"answer": 42}}
        resp = self._make_httpx_response(200, c.endpoint, payload=payload)
        monkeypatch.setattr(c._client, "post", lambda url, json: resp)
        out = c._gql("query { v }", {})
        assert out == {"answer": 42}

    def test_get_event_by_url(self, monkeypatch):
        c = OutsideApiGraphQlClient()
        node = {
            "eventId": "124",
            "name": "ByURL",
            "eventUrl": "u",
            "staticUrl": "s",
            "vanityUrl": "v",
            "appType": "BIKEREG",
            "city": "X",
            "state": "Y",
            "zip": "00000",
            "date": "2026-01-01",
            "eventEndDate": "2026-01-01",
            "openRegDate": "2025-01-01",
            "closeRegDate": "2025-06-01",
            "isOpen": True,
            "isHighlighted": False,
            "latitude": 0.0,
            "longitude": 0.0,
            "eventTypes": [],
        }
        monkeypatch.setattr(c, "_gql", lambda q, v: {"athleticEventByURL": node})
        ev = c.get_event_by_url("https://example.com/e/124")
        assert isinstance(ev, Event)
        assert ev.event_id == 124
        assert ev.name == "ByURL"

    def test_get_event_categories(self, monkeypatch):
        c = OutsideApiGraphQlClient()
        cats = [
            {
                "name": "Cat-1",
                "raceRecId": "R1",
                "startTime": "2026-01-02T07:00:00",
                "distance": "50",
                "distanceUnit": "km",
                "appType": "BIKEREG",
                "eventId": 700,
                "raceDates": ["2026-01-02"],
            }
        ]
        monkeypatch.setattr(c, "_gql", lambda q, v: {"athleticEvent": {"categories": cats}})
        out = c.get_event_categories(700)
        assert len(out) == 1
        assert isinstance(out[0], EventCategory)
        assert out[0].name == "Cat-1"

    def test_get_events_batching_and_missing(self, monkeypatch):
        c = OutsideApiGraphQlClient()

        def fake_gql(q: str, vars_: Dict[str, Any]):
            data = {}
            for k, v in vars_.items():
                if k.startswith("id_"):
                    idx = int(k.split("_")[1])
                    if int(v) == 2:
                        continue  # simulate missing node
                    data[f"e_{idx}"] = {
                        "eventId": str(v),
                        "name": f"E{v}",
                        "eventUrl": "u",
                        "staticUrl": "s",
                        "vanityUrl": "v",
                        "appType": "BIKEREG",
                        "city": "X",
                        "state": "Y",
                        "zip": "00000",
                        "date": "2026-01-01",
                        "eventEndDate": "2026-01-01",
                        "openRegDate": "2025-01-01",
                        "closeRegDate": "2025-06-01",
                        "isOpen": True,
                        "isHighlighted": False,
                        "latitude": 0.0,
                        "longitude": 0.0,
                        "eventTypes": [],
                    }
            return data

        monkeypatch.setattr(c, "_gql", fake_gql)
        out = c.get_events([1, 2, 3], batch_size=2)
        assert [e.event_id if e else None for e in out] == [1, None, 3]

    def test_get_event_types_filters_and_maps(self, monkeypatch):
        c = OutsideApiGraphQlClient()
        items = [
            {
                "typeID": "9",
                "typeDesc": "CX",
                "typePriority": 1,
                "filterableOnCalendar": True,
                "mapKeyColor": "#f00",
                "displayStatusOnMap": "SHOW_ON_MAP",
            },
            "not-a-dict",
        ]
        monkeypatch.setattr(c, "_gql", lambda q, v: {"athleticEventTypes": items})
        out = c.get_event_types([1, 2])
        assert len(out) == 1
        assert isinstance(out[0], EventType)
        assert out[0].type_id == 9

    def test_get_sanctioning_bodies_filters_and_maps(self, monkeypatch):
        c = OutsideApiGraphQlClient()
        items = [{"id": 77, "name": "USAC", "appType": "BIKEREG"}, 42]
        monkeypatch.setattr(c, "_gql", lambda q, v: {"ARegSanctioningBodies": items})
        out = c.get_sanctioning_bodies()
        assert len(out) == 1
        assert isinstance(out[0], SanctioningBody)
        assert out[0].id == 77
        assert out[0].name == "USAC"

    def test_search_calendar_maps_nodes_and_pages(self, monkeypatch):
        c = OutsideApiGraphQlClient()
        node_payload = {
            "id": "node-1",
            "eventId": 999,
            "appType": "BIKEREG",
            "startDate": "2026-05-01",
            "endDate": "2026-05-02",
            "openRegDate": "2025-12-01",
            "closeRegDate": "2026-04-25",
            "name": "CalendarView",
            "city": "X",
            "state": "Y",
            "latitude": 1.0,
            "longitude": 2.0,
            "searchEntryType": "COMPLETE_EVENT",
            "isMembership": 0,
            "promotionLevel": 1,
            "athleticEvent": {
                "eventId": "999",
                "name": "Calendar Event",
                "eventUrl": "u",
                "staticUrl": "s",
                "vanityUrl": "v",
                "appType": "BIKEREG",
                "city": "X",
                "state": "Y",
                "zip": "00000",
                "date": "2026-05-01",
                "eventEndDate": "2026-05-02",
                "openRegDate": "2025-12-01",
                "closeRegDate": "2026-04-25",
                "isOpen": True,
                "isHighlighted": False,
                "latitude": 1.0,
                "longitude": 2.0,
                "eventTypes": ["Gravel"],
            },
        }
        payload = {
            "athleticEventCalendar": {
                "totalCount": 1,
                "pageInfo": {
                    "hasNextPage": True,
                    "hasPreviousPage": False,
                    "startCursor": "A",
                    "endCursor": "B",
                },
                "nodes": [node_payload, "not-a-dict"],
            }
        }
        monkeypatch.setattr(c, "_gql", lambda q, v: payload)

        result = c.search_calendar(
            params={"searchText": "gravel"},
            first=10,
            after=None,
            last=None,
            before=None,
            precache=True,
        )

        assert isinstance(result, CalendarResult)
        assert result.total_count == 1
        assert isinstance(result.page_info, PageInfo)
        assert result.page_info.has_next_page is True
        assert len(result.nodes) == 1
        assert isinstance(result.nodes[0], CalendarNode)
        assert result.nodes[0].event is not None
        assert result.nodes[0].event.name == "Calendar Event"

    def test_get_competitions_list_missing_date_skips(self, monkeypatch, caplog):
        c = OutsideApiGraphQlClient()

        def fake_get_event(_eid: int, precache: bool = True) -> Event:
            return self._make_event(event_id=_eid, date=None, event_end_date=None, categories=[])

        monkeypatch.setattr(OutsideApiGraphQlClient, "get_event", staticmethod(fake_get_event))
        out = c.get_competitions([{"id": 1}])
        assert out == []
        assert "missing usable date" in caplog.text

    def test_get_competitions_race_type_fallbacks(self, monkeypatch):
        c = OutsideApiGraphQlClient()

        def fake_get_event(_eid: int, precache: bool = True) -> Event:
            return self._make_event(event_id=_eid, event_types=["CX"], categories=[])

        monkeypatch.setattr(OutsideApiGraphQlClient, "get_event", staticmethod(fake_get_event))
        out = c.get_competitions([{"id": 5, "priority": "x"}])
        assert out[0]["race_type"] == "CX"
        assert out[0]["priority"] == "B"

    def test_get_competitions_location_optional(self, monkeypatch):
        c = OutsideApiGraphQlClient()

        def fake_get_event(_eid: int, precache: bool = True) -> Event:
            return self._make_event(
                event_id=_eid,
                city=None,
                state=None,
                categories=[self._make_category("X", [dt(2026, 1, 1)])],
            )

        monkeypatch.setattr(OutsideApiGraphQlClient, "get_event", staticmethod(fake_get_event))
        out = c.get_competitions([{"id": 11}])
        assert "location" not in out[0]

    @pytest.mark.parametrize(
        "inp,exp",
        [
            ("A", "A"),
            ("b", "B"),
            ("c", "C"),
            ("", "B"),
            (None, "B"),
            ("Z", "B"),
        ],
    )
    def test__normalize_priority_value(self, inp, exp):
        c = OutsideApiGraphQlClient()
        assert c._normalize_priority_value(inp) == exp

    def test__map_category_event_id_bad_type(self):
        c = OutsideApiGraphQlClient()
        node = {
            "name": "X",
            "raceRecId": "R",
            "startTime": "2026-01-01T08:00:00",
            "distance": "10",
            "distanceUnit": "km",
            "appType": "RUNREG",
            "eventId": {"bad": "type"},  # triggers except/pass path (lines 282-283)
            "raceDates": ["2026-01-01"],
        }
        cat = c._map_category(node)
        assert cat.event_id is None  # stayed None after exception

    def test__gql_transport_error_logs_and_raises(self, monkeypatch):
        c = OutsideApiGraphQlClient()
        req = httpx.Request("POST", c.endpoint)

        def boom_post(url, json):
            raise httpx.ConnectError("boom", request=req)

        monkeypatch.setattr(c._client, "post", boom_post)
        with pytest.raises(httpx.HTTPError):
            c._gql("query { a }", {})  # lines 303-305

    def test__gql_400_errors_field_not_list_fallback(self, monkeypatch):
        c = OutsideApiGraphQlClient()
        payload = {"errors": 123}  # not iterable -> inner try fails -> fallback (lines 326-327)
        resp = self._make_httpx_response(400, c.endpoint, payload=payload)
        monkeypatch.setattr(c._client, "post", lambda url, json: resp)
        with pytest.raises(httpx.HTTPStatusError) as ex:
            c._gql("query { a }", {})
        assert "GraphQL HTTP error 400" in str(ex.value)
        # fallback includes serialized payload
        assert '"errors": 123' in str(ex.value)

    def test__parse_dt_colon_branch_microseconds(self):
        c = OutsideApiGraphQlClient()
        # Forces the colon-offset handling branch (lines 364-368); returns None after failed parse with %f omitted
        s = "2026-04-11T09:10:11.000+05:30"
        assert c._parse_dt(s) is None

    def test__map_event_eventid_object_str_coercion(self):
        c = OutsideApiGraphQlClient()

        class WeirdId:
            def __str__(self):
                return "777"

        node = {
            "eventId": WeirdId(),  # int() fails; int(str(...)) works (lines 390-392)
            "name": "N",
            "eventUrl": "u",
            "staticUrl": "s",
            "vanityUrl": "v",
            "appType": "BIKEREG",
            "city": "X",
            "state": "Y",
            "zip": "0",
            "date": "2026-01-01",
            "eventEndDate": "2026-01-01",
            "openRegDate": "2025-01-01",
            "closeRegDate": "2025-06-01",
            "isOpen": True,
            "isHighlighted": False,
            "latitude": 0.0,
            "longitude": 0.0,
            "eventTypes": [],
        }
        ev = c._map_event(node)
        assert ev.event_id == 777

    def test__map_event_eventid_uncoercible_sets_minus_one(self):
        c = OutsideApiGraphQlClient()
        node = {
            "eventId": {"x": 1},  # both int(...) and int(str(...)) fail -> -1 (lines 393-394)
            "name": "N",
            "eventUrl": "u",
            "staticUrl": "s",
            "vanityUrl": "v",
            "appType": "BIKEREG",
            "city": "X",
            "state": "Y",
            "zip": "0",
            "date": "2026-01-01",
            "eventEndDate": "2026-01-02",
            "openRegDate": "2025-01-01",
            "closeRegDate": "2025-06-01",
            "isOpen": True,
            "isHighlighted": False,
            "latitude": 0.0,
            "longitude": 0.0,
            "eventTypes": [],
        }
        ev = c._map_event(node)
        assert ev.event_id == -1

    def test_get_competitions_dict_empty_section_continue(self):
        c = OutsideApiGraphQlClient()
        # Empty list should trigger 'continue' (line 472)
        out = c.get_competitions({"bikereg": [], "runreg": []})
        assert out == []

    def test_get_competitions_subclient_init_error_logged(self, monkeypatch, caplog):
        root = OutsideApiGraphQlClient()

        def boom_init(*args, **kwargs):
            raise RuntimeError("init-fail")

        monkeypatch.setattr(OutsideApiGraphQlClient, "__init__", boom_init, raising=True)
        out = root.get_competitions({"bikereg": [{"id": 1}]})  # lines 485-486
        assert out == []
        assert "Failed resolving competitions" in caplog.text

    def test_get_competitions_list_empty_returns(self):
        c = OutsideApiGraphQlClient()
        assert c.get_competitions([]) == []  # line 491

    def test_get_competitions_date_string_iso_branch(self, monkeypatch):
        c = OutsideApiGraphQlClient()

        def fake_get_event(_eid: int, precache: bool = True) -> Event:
            # Date as string to hit string split branch (lines 502-503)
            e = self._make_event(event_id=_eid, categories=[])
            object.__setattr__(e, "date", "2026-07-04T12:34:56")
            return e

        monkeypatch.setattr(OutsideApiGraphQlClient, "get_event", staticmethod(fake_get_event))
        out = c.get_competitions([{"id": 10}])
        assert out[0]["date"] == "2026-07-04"

    def test_get_competitions_invalid_entry_skipped(self, caplog):
        c = OutsideApiGraphQlClient()
        out = c.get_competitions([{}])  # lines 514-515
        assert out == []
        assert "requires 'id' or 'url'" in caplog.text

    def test_get_competitions_get_event_raises_warning(self, monkeypatch, caplog):
        c = OutsideApiGraphQlClient()

        def boom_get_event(_eid: int, precache: bool = True):
            raise RuntimeError("fetch fail")

        monkeypatch.setattr(OutsideApiGraphQlClient, "get_event", staticmethod(boom_get_event))
        out = c.get_competitions(
            [{"id": 1}]
        )  # lines 523-525 (except) and 528-529 (event not found warning)
        assert out == []
        assert "Failed to retrieve event" in caplog.text or "event not found" in caplog.text

    def test_get_competitions_categories_provider_raises_for_date_block(self, monkeypatch, caplog):
        c = OutsideApiGraphQlClient()

        def provider_raises(_eid: int):
            raise RuntimeError("cat-fail")

        # No event.date -> date block will try categories (lines 537-538)
        e = self._make_event(event_id=5, date=None, event_end_date=dt(2026, 9, 1), categories=None)
        object.__setattr__(e, "_categories_cache", None)
        object.__setattr__(e, "_categories_provider", provider_raises)

        monkeypatch.setattr(
            OutsideApiGraphQlClient, "get_event", staticmethod(lambda _eid, precache=True: e)
        )
        out = c.get_competitions([{"id": 5}])
        # Fallback to event_end_date used
        assert out[0]["date"] == "2026-09-01"

    def test_get_competitions_categories_provider_raises_for_race_type_block(self, monkeypatch):
        c = OutsideApiGraphQlClient()

        def provider_raises(_eid: int):
            raise RuntimeError("cat-fail")

        # event.date present skips earlier cat path; race_type block will try categories (lines 554-555)
        e = self._make_event(
            event_id=6, date=dt(2026, 10, 1), categories=None, event_types=["TypeX"]
        )
        object.__setattr__(e, "_categories_cache", None)
        object.__setattr__(e, "_categories_provider", provider_raises)

        monkeypatch.setattr(
            OutsideApiGraphQlClient, "get_event", staticmethod(lambda _eid, precache=True: e)
        )
        out = c.get_competitions([{"id": 6}])
        assert out[0]["race_type"] == "TypeX"  # fell back to event_types

    def test_get_competitions_date_obj_iso_branch(self, monkeypatch):
        from datetime import date as _date

        c = OutsideApiGraphQlClient()

        def fake_get_event(_eid: int, precache: bool = True) -> Event:
            e = self._make_event(event_id=_eid, categories=[])
            object.__setattr__(e, "date", _date(2026, 7, 2))  # lines 500 branch
            return e

        monkeypatch.setattr(OutsideApiGraphQlClient, "get_event", staticmethod(fake_get_event))
        out = c.get_competitions([{"id": 12}])
        assert out[0]["date"] == "2026-07-02"
