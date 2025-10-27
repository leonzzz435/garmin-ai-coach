import json
from datetime import datetime as dt
from typing import Any

import httpx
import pytest

from services.outside.client import OutsideApiGraphQlClient
from services.outside.models import (
    CalendarNode,
    CalendarResult,
    Event,
    EventCategory,
    EventType,
    PageInfo,
    SanctioningBody,
)


@pytest.mark.unit
class TestOutsideApiGraphQlClient:
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
        status: int, url: str, payload: dict[str, Any] | None = None, content: bytes | None = None
    ):
        request = httpx.Request("POST", url)
        if payload is not None:
            content = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"} if payload is not None else {}
        return httpx.Response(status, request=request, content=content or b"", headers=headers)

    def test_init_default_and_validation(self):
        client = OutsideApiGraphQlClient()
        assert client.app_type == "BIKEREG"

        client_runreg = OutsideApiGraphQlClient(app_type="runreg")
        assert client_runreg.app_type == "RUNREG"

        with pytest.raises(ValueError):
            OutsideApiGraphQlClient(app_type="OUTSIDE_API")

    def test__gql_200_with_graphql_errors_raises_runtimeerror(self, monkeypatch):
        client = OutsideApiGraphQlClient()
        json_module = json

        def fake_post(url: str, json: dict[str, Any]):
            return httpx.Response(
                200,
                request=httpx.Request("POST", url),
                content=json_module.dumps({"errors": [{"message": "Something went wrong"}]}).encode("utf-8")
            )

        monkeypatch.setattr(client._client, "post", fake_post)

        with pytest.raises(RuntimeError) as exception:
            client._gql("query Q { x }", {})
        assert "Something went wrong" in str(exception.value)

    def test__gql_400_with_errors_raises_httpstatusexterror(self, monkeypatch):
        client = OutsideApiGraphQlClient()
        json_module = json

        def fake_post(url: str, json: dict[str, Any]):
            return httpx.Response(
                400,
                request=httpx.Request("POST", url),
                content=json_module.dumps({"errors": [{"message": "Bad variable for appType"}]}).encode("utf-8")
            )

        monkeypatch.setattr(client._client, "post", fake_post)

        with pytest.raises(httpx.HTTPStatusError) as exception:
            client._gql("query Q { x }", {})
        assert "GraphQL HTTP error 400" in str(exception.value)
        assert "Bad variable for appType" in str(exception.value)

    def test_get_event_mapping_via__gql(self, monkeypatch):
        client = OutsideApiGraphQlClient()

        event_payload = {
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

        def fake_gql(query: str, variables: dict[str, Any]):
            assert "athleticEvent" in query
            return {"athleticEvent": event_payload}

        monkeypatch.setattr(client, "_gql", fake_gql)

        event = client.get_event(71252, precache=True)
        assert isinstance(event, Event)
        assert event.event_id == 71252
        assert event.name == "Sunflower Gravel"
        assert event.city == "Lawrence"
        assert event.state == "KS"
        categories = event.categories
        assert isinstance(categories, list) and len(categories) == 1
        assert isinstance(categories[0], EventCategory)
        assert categories[0].name == "100k"

    def test_get_competitions_list_by_id_and_url(self, monkeypatch):
        def build_event_by_id():
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

        def fake_get_event(event_id: int, precache: bool = False):
            assert precache is True
            return build_event_by_id()

        def fake_get_event_by_url(url: str, precache: bool = False):
            assert precache is True
            return build_event_by_url()

        monkeypatch.setattr(client, "get_event", fake_get_event)
        monkeypatch.setattr(client, "get_event_by_url", fake_get_event_by_url)

        competitions = client.get_competitions([
            {"id": 1, "priority": "A", "target_time": "3:00:00"},
            {"url": "https://www.runreg.com/abc"},
        ])

        assert len(competitions) == 2

        competition_by_id = competitions[0]
        assert competition_by_id["name"] == "Bike Event By ID"
        assert competition_by_id["date"] == "2026-05-09"
        assert competition_by_id["race_type"] == "Gravel 100"
        assert competition_by_id["priority"] == "A"
        assert competition_by_id["target_time"] == "3:00:00"
        assert competition_by_id.get("location") == "Boulder, CO"

        competition_by_url = competitions[1]
        assert competition_by_url["name"] == "Run Event By URL"
        assert competition_by_url["date"] == "2026-06-01"
        assert competition_by_url["race_type"] == "Half Marathon"
        assert competition_by_url["priority"] == "B"
        assert competition_by_url.get("location") == "Boston, MA"

    def test_get_competitions_dispatch_dict_sections(self, monkeypatch):
        def fake_get_event(self, eid: int, precache: bool = False):
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

        monkeypatch.setattr(OutsideApiGraphQlClient, "get_event", fake_get_event, raising=True)
        monkeypatch.setattr(
            OutsideApiGraphQlClient, "get_event_by_url", fake_get_event_by_url, raising=True
        )

        root_client = OutsideApiGraphQlClient()
        competitions = root_client.get_competitions({
            "bikereg": [{"id": 1}],
            "runreg": [{"url": "https://www.runreg.com/foo"}],
            "unknown": [{"id": 123}],
        })
        assert len(competitions) == 2
        assert sorted([comp["name"] for comp in competitions]) == ["BIKEREG-ID-1", "RUNREG-URL"]

    def test_get_competitions_unknown_section_ignored(self, monkeypatch):
        client = OutsideApiGraphQlClient()
        competitions = client.get_competitions({"unknown": [{"id": 1}]})
        assert competitions == []

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
        client = OutsideApiGraphQlClient()
        result = client._parse_dt(val)
        assert (result is None) == expect_none
        if result is not None:
            assert isinstance(result, dt)

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
        client = OutsideApiGraphQlClient()
        assert client._to_float(inp) == expected

    def test__chunks_basic(self):
        client = OutsideApiGraphQlClient()
        sequence = list(range(7))
        chunks = list(client._chunks(sequence, 3))
        assert chunks == [[0, 1, 2], [3, 4, 5], [6]]

    def test__map_category_parses_dates_and_starttime(self):
        client = OutsideApiGraphQlClient()
        category_node = {
            "name": "Marathon",
            "raceRecId": "R1",
            "startTime": "2026-02-01T08:00:00",
            "distance": "26.2",
            "distanceUnit": "miles",
            "appType": "RUNREG",
            "eventId": 123,
            "raceDates": ["2026-02-01", "2026-02-02T09:30:00"],
        }
        category = client._map_category(category_node)
        assert category.name == "Marathon"
        assert category.event_id == 123
        assert len(category.race_dates) == 2
        assert category.start_time is not None

    def test__map_event_inline_categories_precache(self):
        client = OutsideApiGraphQlClient()
        event_node = {
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
        event = client._map_event(event_node, precache_categories=True)
        assert isinstance(event, Event)
        assert event.event_id == 555
        assert len(event.categories) == 1
        assert event.categories[0].name == "Cat A"

    def test__map_event_provider_precache_and_provider_error(self, caplog):
        client = OutsideApiGraphQlClient()
        event_node = {
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

        def bad_provider(event_id: int) -> list[EventCategory]:
            raise RuntimeError("boom")

        event = client._map_event(event_node, categories_provider=bad_provider, precache_categories=True)
        assert isinstance(event, Event)
        assert event.event_id == 556
        assert event.categories == []
        assert any("Failed to precache categories" in line for line in caplog.text.splitlines())

    def test__map_event_no_dict_returns_none(self):
        client = OutsideApiGraphQlClient()
        assert client._map_event(None) is None

    def test__map_event_type_mapping(self):
        client = OutsideApiGraphQlClient()
        event_type_node = {
            "typeID": "7",
            "typeDesc": "Gravel",
            "typePriority": 10,
            "filterableOnCalendar": True,
            "mapKeyColor": "#00FF00",
            "displayStatusOnMap": "SHOW_ON_MAP",
        }
        event_type = client._map_event_type(event_type_node)
        assert isinstance(event_type, EventType)
        assert event_type.type_id == 7
        assert event_type.description == "Gravel"
        assert event_type.filterable_on_calendar is True

    def test__gql_http_500_parse_error(self, monkeypatch):
        client = OutsideApiGraphQlClient()
        response = self._make_httpx_response(
            500, client.endpoint, payload=None, content=b"<html>oops</html>"
        )
        monkeypatch.setattr(client._client, "post", lambda url, json: response)
        with pytest.raises(httpx.HTTPStatusError) as exception_info:
            client._gql("query { y }", {})
        message = str(exception_info.value)
        assert "GraphQL HTTP error 500" in message
        assert "failed to parse JSON errors" in message

    def test__gql_200_success_returns_data(self, monkeypatch):
        client = OutsideApiGraphQlClient()
        response = self._make_httpx_response(200, client.endpoint, payload={"data": {"answer": 42}})
        monkeypatch.setattr(client._client, "post", lambda url, json: response)
        result = client._gql("query { v }", {})
        assert result == {"answer": 42}

    def test_get_event_by_url(self, monkeypatch):
        client = OutsideApiGraphQlClient()
        event_node = {
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
        monkeypatch.setattr(client, "_gql", lambda query, variables: {"athleticEventByURL": event_node})
        event = client.get_event_by_url("https://example.com/e/124")
        assert isinstance(event, Event)
        assert event.event_id == 124
        assert event.name == "ByURL"

    def test_get_event_categories(self, monkeypatch):
        client = OutsideApiGraphQlClient()
        categories_data = [
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
        monkeypatch.setattr(client, "_gql", lambda query, variables: {"athleticEvent": {"categories": categories_data}})
        categories = client.get_event_categories(700)
        assert len(categories) == 1
        assert isinstance(categories[0], EventCategory)
        assert categories[0].name == "Cat-1"

    def test_get_events_batching_and_missing(self, monkeypatch):
        client = OutsideApiGraphQlClient()

        def fake_gql(query: str, variables: dict[str, Any]):
            data = {}
            for key, value in variables.items():
                if key.startswith("id_"):
                    index = int(key.split("_")[1])
                    if int(value) == 2:
                        continue
                    data[f"e_{index}"] = {
                        "eventId": str(value),
                        "name": f"E{value}",
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

        monkeypatch.setattr(client, "_gql", fake_gql)
        events = client.get_events([1, 2, 3], batch_size=2)
        assert [event.event_id if event else None for event in events] == [1, None, 3]

    def test_get_event_types_filters_and_maps(self, monkeypatch):
        client = OutsideApiGraphQlClient()
        event_types_data = [
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
        monkeypatch.setattr(client, "_gql", lambda query, variables: {"athleticEventTypes": event_types_data})
        event_types = client.get_event_types([1, 2])
        assert len(event_types) == 1
        assert isinstance(event_types[0], EventType)
        assert event_types[0].type_id == 9

    def test_get_sanctioning_bodies_filters_and_maps(self, monkeypatch):
        client = OutsideApiGraphQlClient()
        sanctioning_bodies_data = [{"id": 77, "name": "USAC", "appType": "BIKEREG"}, 42]
        monkeypatch.setattr(client, "_gql", lambda query, variables: {"ARegSanctioningBodies": sanctioning_bodies_data})
        sanctioning_bodies = client.get_sanctioning_bodies()
        assert len(sanctioning_bodies) == 1
        assert isinstance(sanctioning_bodies[0], SanctioningBody)
        assert sanctioning_bodies[0].id == 77
        assert sanctioning_bodies[0].name == "USAC"

    def test_search_calendar_maps_nodes_and_pages(self, monkeypatch):
        client = OutsideApiGraphQlClient()
        calendar_node_payload = {
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
                "nodes": [calendar_node_payload, "not-a-dict"],
            }
        }
        monkeypatch.setattr(client, "_gql", lambda query, variables: payload)

        result = client.search_calendar(
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
        client = OutsideApiGraphQlClient()

        def fake_get_event(event_id: int, precache: bool = True) -> Event:
            return self._make_event(event_id=event_id, date=None, event_end_date=None, categories=[])

        monkeypatch.setattr(OutsideApiGraphQlClient, "get_event", staticmethod(fake_get_event))
        competitions = client.get_competitions([{"id": 1}])
        assert competitions == []
        assert "missing usable date" in caplog.text

    def test_get_competitions_race_type_fallbacks(self, monkeypatch):
        client = OutsideApiGraphQlClient()

        def fake_get_event(event_id: int, precache: bool = True) -> Event:
            return self._make_event(event_id=event_id, event_types=["CX"], categories=[])

        monkeypatch.setattr(OutsideApiGraphQlClient, "get_event", staticmethod(fake_get_event))
        competitions = client.get_competitions([{"id": 5, "priority": "x"}])
        assert competitions[0]["race_type"] == "CX"
        assert competitions[0]["priority"] == "B"

    def test_get_competitions_location_optional(self, monkeypatch):
        client = OutsideApiGraphQlClient()

        def fake_get_event(event_id: int, precache: bool = True) -> Event:
            return self._make_event(
                event_id=event_id,
                city=None,
                state=None,
                categories=[self._make_category("X", [dt(2026, 1, 1)])],
            )

        monkeypatch.setattr(OutsideApiGraphQlClient, "get_event", staticmethod(fake_get_event))
        competitions = client.get_competitions([{"id": 11}])
        assert "location" not in competitions[0]

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
        client = OutsideApiGraphQlClient()
        assert client._normalize_priority_value(inp) == exp

    def test__map_category_event_id_bad_type(self):
        client = OutsideApiGraphQlClient()
        category_node = {
            "name": "X",
            "raceRecId": "R",
            "startTime": "2026-01-01T08:00:00",
            "distance": "10",
            "distanceUnit": "km",
            "appType": "RUNREG",
            "eventId": {"bad": "type"},
            "raceDates": ["2026-01-01"],
        }
        category = client._map_category(category_node)
        assert category.event_id is None

    def test__gql_transport_error_logs_and_raises(self, monkeypatch):
        client = OutsideApiGraphQlClient()
        request = httpx.Request("POST", client.endpoint)

        def boom_post(url, json):
            raise httpx.ConnectError("boom", request=request)

        monkeypatch.setattr(client._client, "post", boom_post)
        with pytest.raises(httpx.HTTPError):
            client._gql("query { a }", {})

    def test__gql_400_errors_field_not_list_fallback(self, monkeypatch):
        client = OutsideApiGraphQlClient()
        response = self._make_httpx_response(400, client.endpoint, payload={"errors": 123})
        monkeypatch.setattr(client._client, "post", lambda url, json: response)
        with pytest.raises(httpx.HTTPStatusError) as exception:
            client._gql("query { a }", {})
        assert "GraphQL HTTP error 400" in str(exception.value)
        assert '"errors": 123' in str(exception.value)

    def test__parse_dt_colon_branch_microseconds(self):
        client = OutsideApiGraphQlClient()
        datetime_string = "2026-04-11T09:10:11.000+05:30"
        assert client._parse_dt(datetime_string) is None

    def test__map_event_eventid_object_str_coercion(self):
        client = OutsideApiGraphQlClient()

        class WeirdId:
            def __str__(self):
                return "777"

        event_node = {
            "eventId": WeirdId(),
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
        event = client._map_event(event_node)
        assert event.event_id == 777

    def test__map_event_eventid_uncoercible_sets_minus_one(self):
        client = OutsideApiGraphQlClient()
        event_node = {
            "eventId": {"x": 1},
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
        event = client._map_event(event_node)
        assert event.event_id == -1

    def test_get_competitions_dict_empty_section_continue(self):
        client = OutsideApiGraphQlClient()
        competitions = client.get_competitions({"bikereg": [], "runreg": []})
        assert competitions == []

    def test_get_competitions_subclient_init_error_logged(self, monkeypatch, caplog):
        root_client = OutsideApiGraphQlClient()

        def boom_init(*args, **kwargs):
            raise RuntimeError("init-fail")

        monkeypatch.setattr(OutsideApiGraphQlClient, "__init__", boom_init, raising=True)
        competitions = root_client.get_competitions({"bikereg": [{"id": 1}]})
        assert competitions == []
        assert "Failed resolving competitions" in caplog.text

    def test_get_competitions_list_empty_returns(self):
        client = OutsideApiGraphQlClient()
        assert client.get_competitions([]) == []

    def test_get_competitions_date_string_iso_branch(self, monkeypatch):
        client = OutsideApiGraphQlClient()

        def fake_get_event(event_id: int, precache: bool = True) -> Event:
            event = self._make_event(event_id=event_id, categories=[])
            object.__setattr__(event, "date", "2026-07-04T12:34:56")
            return event

        monkeypatch.setattr(OutsideApiGraphQlClient, "get_event", staticmethod(fake_get_event))
        competitions = client.get_competitions([{"id": 10}])
        assert competitions[0]["date"] == "2026-07-04"

    def test_get_competitions_invalid_entry_skipped(self, caplog):
        client = OutsideApiGraphQlClient()
        competitions = client.get_competitions([{}])
        assert competitions == []
        assert "requires 'id' or 'url'" in caplog.text

    def test_get_competitions_get_event_raises_warning(self, monkeypatch, caplog):
        client = OutsideApiGraphQlClient()

        def boom_get_event(event_id: int, precache: bool = True):
            raise RuntimeError("fetch fail")

        monkeypatch.setattr(OutsideApiGraphQlClient, "get_event", staticmethod(boom_get_event))
        competitions = client.get_competitions([{"id": 1}])
        assert competitions == []
        assert "Failed to retrieve event" in caplog.text or "event not found" in caplog.text

    def test_get_competitions_categories_provider_raises_for_date_block(self, monkeypatch, caplog):
        client = OutsideApiGraphQlClient()

        def provider_raises(event_id: int):
            raise RuntimeError("cat-fail")

        event = self._make_event(event_id=5, date=None, event_end_date=dt(2026, 9, 1), categories=None)
        object.__setattr__(event, "_categories_cache", None)
        object.__setattr__(event, "_categories_provider", provider_raises)

        monkeypatch.setattr(
            OutsideApiGraphQlClient, "get_event", staticmethod(lambda event_id, precache=True: event)
        )
        competitions = client.get_competitions([{"id": 5}])
        assert competitions[0]["date"] == "2026-09-01"

    def test_get_competitions_categories_provider_raises_for_race_type_block(self, monkeypatch):
        client = OutsideApiGraphQlClient()

        def provider_raises(event_id: int):
            raise RuntimeError("cat-fail")

        event = self._make_event(
            event_id=6, date=dt(2026, 10, 1), categories=None, event_types=["TypeX"]
        )
        object.__setattr__(event, "_categories_cache", None)
        object.__setattr__(event, "_categories_provider", provider_raises)

        monkeypatch.setattr(
            OutsideApiGraphQlClient, "get_event", staticmethod(lambda event_id, precache=True: event)
        )
        competitions = client.get_competitions([{"id": 6}])
        assert competitions[0]["race_type"] == "TypeX"

    def test_get_competitions_date_obj_iso_branch(self, monkeypatch):
        from datetime import date as date_type

        client = OutsideApiGraphQlClient()

        def fake_get_event(event_id: int, precache: bool = True) -> Event:
            event = self._make_event(event_id=event_id, categories=[])
            object.__setattr__(event, "date", date_type(2026, 7, 2))
            return event

        monkeypatch.setattr(OutsideApiGraphQlClient, "get_event", staticmethod(fake_get_event))
        competitions = client.get_competitions([{"id": 12}])
        assert competitions[0]["date"] == "2026-07-02"
