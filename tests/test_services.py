"""Tests for the kakao_map services and point-input resolution."""

from __future__ import annotations

from datetime import timedelta

import pytest
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.kakao_map.const import (
    BIKESET_ROUTE_URL,
    CARS_ROUTE_URL,
    CATEGORY_SEARCH_URL,
    DOMAIN,
    KEYWORD_SEARCH_URL,
    PUBTRANS_ROUTE_URL,
    TRANSCOORD_URL,
)
from custom_components.kakao_map.helpers import (
    ResolvedPoint,
    resolve_point,
    resolve_waypoint,
)

STARBUCKS_DOC = {
    "place_name": "스타벅스 판교점",
    "x": "127.1112",
    "y": "37.3945",
    "address_name": "경기 성남시 분당구 삼평동 681",
    "road_address_name": "경기 성남시 분당구 판교역로 4",
    "place_url": "http://place.map.kakao.com/26338954",
}


async def _setup_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Set up a kakao_map config entry so services are registered."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "test-key"}, unique_id=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_search_place_returns_result_list(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """search_place returns each document mapped to the SPEC response schema."""
    await _setup_integration(hass)
    other_doc = {**STARBUCKS_DOC, "place_name": "스타벅스 판교역점"}
    aioclient_mock.get(KEYWORD_SEARCH_URL, json={"documents": [STARBUCKS_DOC, other_doc]})

    response = await hass.services.async_call(
        DOMAIN,
        "search_place",
        {"query": "판교 스타벅스"},
        blocking=True,
        return_response=True,
    )

    assert response == {
        "results": [
            {
                "place_name": "스타벅스 판교점",
                "latitude": 37.3945,
                "longitude": 127.1112,
                "address": "경기 성남시 분당구 삼평동 681",
                "road_address": "경기 성남시 분당구 판교역로 4",
                "place_url": "http://place.map.kakao.com/26338954",
                "map_url": "https://map.kakao.com/link/map/스타벅스 판교점,37.3945,127.1112",
            },
            {
                "place_name": "스타벅스 판교역점",
                "latitude": 37.3945,
                "longitude": 127.1112,
                "address": "경기 성남시 분당구 삼평동 681",
                "road_address": "경기 성남시 분당구 판교역로 4",
                "place_url": "http://place.map.kakao.com/26338954",
                "map_url": "https://map.kakao.com/link/map/스타벅스 판교역점,37.3945,127.1112",
            },
        ]
    }
    assert aioclient_mock.mock_calls[-1][3]["Authorization"] == "KakaoAK test-key"


async def test_search_place_caps_at_five_results(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """search_place returns at most the top 5 documents."""
    await _setup_integration(hass)
    docs = [{**STARBUCKS_DOC, "place_name": f"스타벅스 {i}호점"} for i in range(7)]
    aioclient_mock.get(KEYWORD_SEARCH_URL, json={"documents": docs})

    response = await hass.services.async_call(
        DOMAIN,
        "search_place",
        {"query": "스타벅스"},
        blocking=True,
        return_response=True,
    )

    assert [r["place_name"] for r in response["results"]] == [
        "스타벅스 0호점",
        "스타벅스 1호점",
        "스타벅스 2호점",
        "스타벅스 3호점",
        "스타벅스 4호점",
    ]


async def test_search_nearby_by_category(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """search_nearby with a category code searches around the center by distance."""
    await _setup_integration(hass)
    hass.states.async_set(
        "zone.home", "zoning", {"latitude": 37.5663, "longitude": 126.9779, "friendly_name": "집"}
    )
    doc = {**STARBUCKS_DOC, "place_name": "GS25 시청점", "distance": "120"}
    aioclient_mock.get(CATEGORY_SEARCH_URL, json={"documents": [doc]})

    response = await hass.services.async_call(
        DOMAIN,
        "search_nearby",
        {"center": "zone.home", "category": "CS2", "radius": 500},
        blocking=True,
        return_response=True,
    )

    assert response["results"][0]["place_name"] == "GS25 시청점"
    assert response["results"][0]["distance"] == 120
    query = aioclient_mock.mock_calls[-1][1].query
    assert query["category_group_code"] == "CS2"
    assert query["x"] == "126.9779"
    assert query["radius"] == "500"


async def test_search_nearby_by_query(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """search_nearby with a keyword biases the keyword search to the center."""
    await _setup_integration(hass)
    nearby_doc = {**STARBUCKS_DOC, "distance": "50"}
    aioclient_mock.get(KEYWORD_SEARCH_URL, json={"documents": [nearby_doc]})

    response = await hass.services.async_call(
        DOMAIN,
        "search_nearby",
        {"center": {"latitude": 37.5663, "longitude": 126.9779}, "query": "스타벅스"},
        blocking=True,
        return_response=True,
    )

    assert response["results"][0]["place_name"] == "스타벅스 판교점"
    assert response["results"][0]["distance"] == 50
    query = aioclient_mock.mock_calls[-1][1].query
    assert query["query"] == "스타벅스"
    assert query["radius"] == "1000"  # DEFAULT_NEARBY_RADIUS


async def test_search_nearby_requires_exactly_one_of_category_or_query(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """search_nearby rejects a call with neither (or both) category and query."""
    await _setup_integration(hass)

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            "search_nearby",
            {"center": {"latitude": 37.5, "longitude": 127.0}},
            blocking=True,
            return_response=True,
        )

    assert err.value.translation_key == "nearby_input"


async def test_search_nearby_no_results(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """search_nearby raises a validation error when nothing is found nearby."""
    await _setup_integration(hass)
    aioclient_mock.get(CATEGORY_SEARCH_URL, json={"documents": []})

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            "search_nearby",
            {"center": {"latitude": 37.5, "longitude": 127.0}, "category": "CE7"},
            blocking=True,
            return_response=True,
        )

    assert err.value.translation_key == "no_results"


async def test_search_place_no_results(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """search_place raises a validation error when the search returns nothing."""
    await _setup_integration(hass)
    aioclient_mock.get(KEYWORD_SEARCH_URL, json={"documents": []})

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            "search_place",
            {"query": "존재하지않는장소12345"},
            blocking=True,
            return_response=True,
        )

    assert err.value.translation_key == "no_results"
    assert err.value.translation_placeholders == {"query": "존재하지않는장소12345"}


async def test_search_place_api_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """search_place surfaces API failures as a HomeAssistantError."""
    await _setup_integration(hass)
    aioclient_mock.get(KEYWORD_SEARCH_URL, status=500)

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN,
            "search_place",
            {"query": "판교 스타벅스"},
            blocking=True,
            return_response=True,
        )

    assert err.value.translation_key == "api_error"


async def test_search_place_removed_on_unload(hass: HomeAssistant) -> None:
    """Unloading the entry removes the search_place service."""
    entry = await _setup_integration(hass)
    assert hass.services.has_service(DOMAIN, "search_place")

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.services.has_service(DOMAIN, "search_place")


async def test_resolve_entity_with_coordinates(hass: HomeAssistant) -> None:
    """An entity with latitude/longitude resolves to its coords and friendly name."""
    hass.states.async_set(
        "device_tracker.my_phone",
        "home",
        {"latitude": 37.5665, "longitude": 126.978, "friendly_name": "내 폰"},
    )

    point = resolve_point(hass, role="출발지", value="device_tracker.my_phone")

    assert point == ResolvedPoint(name="내 폰", latitude=37.5665, longitude=126.978)


async def test_resolve_entity_without_coordinates(hass: HomeAssistant) -> None:
    """An entity lacking coordinate attributes raises an error naming the entity."""
    hass.states.async_set("sensor.no_location", "on", {"friendly_name": "센서"})

    with pytest.raises(ServiceValidationError) as err:
        resolve_point(hass, role="출발지", value="sensor.no_location")

    assert err.value.translation_key == "entity_missing_coordinates"
    assert err.value.translation_placeholders == {"entity_id": "sensor.no_location"}


async def test_resolve_entity_not_found(hass: HomeAssistant) -> None:
    """An unknown entity_id raises an error naming the entity."""
    with pytest.raises(ServiceValidationError) as err:
        resolve_point(hass, role="도착지", value="zone.nowhere")

    assert err.value.translation_key == "entity_not_found"
    assert err.value.translation_placeholders == {"entity_id": "zone.nowhere"}


async def test_resolve_location_dict(hass: HomeAssistant) -> None:
    """A location mapping resolves with the role as its name."""
    point = resolve_point(hass, role="출발지", value={"latitude": 37.5, "longitude": 127.0})

    assert point == ResolvedPoint(name="출발지", latitude=37.5, longitude=127.0)


async def test_resolve_location_ignores_radius(hass: HomeAssistant) -> None:
    """A radius component in the location mapping is ignored."""
    point = resolve_point(
        hass,
        role="도착지",
        value={"latitude": 37.4, "longitude": 127.1, "radius": 100},
    )

    assert point == ResolvedPoint(name="도착지", latitude=37.4, longitude=127.1)


@pytest.mark.parametrize(
    "value",
    [
        {"latitude": 37.5},
        {"latitude": "abc", "longitude": 127.0},
        [37.5, 127.0],
        42,
    ],
)
async def test_resolve_location_invalid(hass: HomeAssistant, value: object) -> None:
    """A non-entity value without numeric latitude and longitude raises an error."""
    with pytest.raises(ServiceValidationError) as err:
        resolve_point(hass, role="출발지", value=value)

    assert err.value.translation_key == "invalid_location"
    assert err.value.translation_placeholders["role"] == "출발지"


async def test_resolve_missing_value(hass: HomeAssistant) -> None:
    """Omitting the point value raises an error naming the role."""
    with pytest.raises(ServiceValidationError) as err:
        resolve_point(hass, role="도착지")

    assert err.value.translation_key == "point_input_missing"
    assert err.value.translation_placeholders == {"role": "도착지"}


async def test_resolve_waypoint_entity(hass: HomeAssistant) -> None:
    """A waypoint given as an entity_id resolves from its attributes."""
    hass.states.async_set(
        "zone.office",
        "zoning",
        {"latitude": 37.4, "longitude": 127.1, "friendly_name": "회사"},
    )

    point = resolve_waypoint(hass, "zone.office", index=1)

    assert point == ResolvedPoint(name="회사", latitude=37.4, longitude=127.1)


async def test_resolve_waypoint_location(hass: HomeAssistant) -> None:
    """A waypoint given as a location mapping resolves with a numbered name."""
    point = resolve_waypoint(hass, {"latitude": 37.39, "longitude": 127.11}, index=2)

    assert point == ResolvedPoint(name="경유지2", latitude=37.39, longitude=127.11)


@pytest.mark.parametrize("value", [{"latitude": 37.5}, [], 42])
async def test_resolve_waypoint_invalid(hass: HomeAssistant, value: object) -> None:
    """A waypoint that is neither an entity_id nor a valid location raises an error."""
    with pytest.raises(ServiceValidationError) as err:
        resolve_waypoint(hass, value, index=1)

    assert err.value.translation_key == "invalid_location"
    assert err.value.translation_placeholders["role"] == "경유지1"


async def test_get_directions_builds_car_link_and_legs(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """get_directions returns the official route URL, legs, and null ETA fields."""
    await _setup_integration(hass)
    aioclient_mock.get(CARS_ROUTE_URL, status=500)

    response = await hass.services.async_call(
        DOMAIN,
        "get_directions",
        {
            "origin": {"latitude": 37.5, "longitude": 127.0},
            "destination": {"latitude": 37.4, "longitude": 127.1},
        },
        blocking=True,
        return_response=True,
    )

    assert response == {
        "route_url": "https://map.kakao.com/link/by/car/출발지,37.5,127.0/도착지,37.4,127.1",
        "mode": "car",
        "duration": None,
        "distance": None,
        "arrival_time": None,
        "legs": [
            {
                "from": "출발지",
                "from_latitude": 37.5,
                "from_longitude": 127.0,
                "to": "도착지",
                "to_latitude": 37.4,
                "to_longitude": 127.1,
            }
        ],
    }


@pytest.mark.parametrize("mode", ["car", "traffic", "walk", "bicycle"])
async def test_get_directions_mode_token_in_url(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, mode: str
) -> None:
    """Each travel mode produces the matching link/by/{mode} URL token."""
    await _setup_integration(hass)
    aioclient_mock.get(CARS_ROUTE_URL, status=500)
    aioclient_mock.get(TRANSCOORD_URL, status=500)

    response = await hass.services.async_call(
        DOMAIN,
        "get_directions",
        {
            "origin": {"latitude": 37.5, "longitude": 127.0},
            "destination": {"latitude": 37.4, "longitude": 127.1},
            "mode": mode,
        },
        blocking=True,
        return_response=True,
    )

    assert response["mode"] == mode
    assert response["route_url"] == (
        f"https://map.kakao.com/link/by/{mode}/출발지,37.5,127.0/도착지,37.4,127.1"
    )


async def test_get_directions_orders_waypoints_between_endpoints(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Waypoints appear in order between origin and destination in URL and legs."""
    await _setup_integration(hass)
    aioclient_mock.get(CARS_ROUTE_URL, status=500)

    response = await hass.services.async_call(
        DOMAIN,
        "get_directions",
        {
            "origin": {"latitude": 37.5, "longitude": 127.0},
            "waypoints": [
                {"latitude": 37.39, "longitude": 127.11},
                {"latitude": 37.41, "longitude": 127.12},
            ],
            "destination": {"latitude": 37.4, "longitude": 127.1},
        },
        blocking=True,
        return_response=True,
    )

    assert response["route_url"] == (
        "https://map.kakao.com/link/by/car/"
        "출발지,37.5,127.0/경유지1,37.39,127.11/경유지2,37.41,127.12/도착지,37.4,127.1"
    )
    assert [leg["from"] for leg in response["legs"]] == ["출발지", "경유지1", "경유지2"]
    assert [leg["to"] for leg in response["legs"]] == ["경유지1", "경유지2", "도착지"]


async def test_get_directions_mixes_entity_and_coords(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """An entity origin and a coordinate destination resolve into one route."""
    await _setup_integration(hass)
    aioclient_mock.get(CARS_ROUTE_URL, status=500)
    hass.states.async_set(
        "zone.home",
        "zoning",
        {"latitude": 37.5, "longitude": 127.0, "friendly_name": "집"},
    )

    response = await hass.services.async_call(
        DOMAIN,
        "get_directions",
        {
            "origin": "zone.home",
            "destination": {"latitude": 37.4, "longitude": 127.1},
        },
        blocking=True,
        return_response=True,
    )

    assert response["route_url"] == (
        "https://map.kakao.com/link/by/car/집,37.5,127.0/도착지,37.4,127.1"
    )


async def test_get_directions_traffic_rejects_waypoints(hass: HomeAssistant) -> None:
    """Public transit mode with waypoints raises a validation error."""
    await _setup_integration(hass)

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            "get_directions",
            {
                "origin": {"latitude": 37.5, "longitude": 127.0},
                "destination": {"latitude": 37.4, "longitude": 127.1},
                "waypoints": [{"latitude": 37.39, "longitude": 127.11}],
                "mode": "traffic",
            },
            blocking=True,
            return_response=True,
        )

    assert err.value.translation_key == "traffic_no_waypoints"


async def test_get_directions_rejects_more_than_five_waypoints(
    hass: HomeAssistant,
) -> None:
    """More than five waypoints raises a validation error before resolution."""
    await _setup_integration(hass)

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            "get_directions",
            {
                "origin": {"latitude": 37.5, "longitude": 127.0},
                "destination": {"latitude": 37.4, "longitude": 127.1},
                "waypoints": [{"latitude": 37.0 + i, "longitude": 127.0} for i in range(6)],
            },
            blocking=True,
            return_response=True,
        )

    assert err.value.translation_key == "too_many_waypoints"


async def test_get_directions_car_populates_eta(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A car route fills duration, distance, and arrival_time from cars.json."""
    await _setup_integration(hass)
    aioclient_mock.get(
        CARS_ROUTE_URL,
        json=[{"resultCode": "SUCCESS", "summary": {"duration": 1195, "distance": 10109}}],
    )

    before = dt_util.now()
    response = await hass.services.async_call(
        DOMAIN,
        "get_directions",
        {
            "origin": {"latitude": 37.5663, "longitude": 126.9779},
            "destination": {"latitude": 37.4979, "longitude": 127.0276},
        },
        blocking=True,
        return_response=True,
    )
    after = dt_util.now()

    assert response["duration"] == 1195
    assert response["distance"] == 10109
    arrival = dt_util.parse_datetime(response["arrival_time"])
    assert arrival is not None
    assert before + timedelta(seconds=1195) <= arrival <= after + timedelta(seconds=1195)


async def test_get_directions_car_degrades_but_keeps_link(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """When cars.json fails, ETA fields are null but the route link is still returned."""
    await _setup_integration(hass)
    aioclient_mock.get(CARS_ROUTE_URL, status=500)

    response = await hass.services.async_call(
        DOMAIN,
        "get_directions",
        {
            "origin": {"latitude": 37.5663, "longitude": 126.9779},
            "destination": {"latitude": 37.4979, "longitude": 127.0276},
        },
        blocking=True,
        return_response=True,
    )

    assert response["duration"] is None
    assert response["distance"] is None
    assert response["arrival_time"] is None
    assert response["route_url"] == (
        "https://map.kakao.com/link/by/car/출발지,37.5663,126.9779/도착지,37.4979,127.0276"
    )


async def test_get_directions_bicycle_populates_eta(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A bicycle route transcoords both points and fills ETA from bikeset.json."""
    await _setup_integration(hass)
    aioclient_mock.get(TRANSCOORD_URL, json={"documents": [{"x": 495119, "y": 1129657}]})
    aioclient_mock.get(
        BIKESET_ROUTE_URL,
        json={"resultCode": "SUCCESS", "directions": [{"time": 3531, "length": 14479}]},
    )

    response = await hass.services.async_call(
        DOMAIN,
        "get_directions",
        {
            "origin": {"latitude": 37.5663, "longitude": 126.9779},
            "destination": {"latitude": 37.4979, "longitude": 127.0276},
            "mode": "bicycle",
        },
        blocking=True,
        return_response=True,
    )

    assert response["duration"] == 3531
    assert response["distance"] == 14479
    assert response["arrival_time"] is not None


async def test_get_directions_bicycle_with_waypoints_skips_eta(
    hass: HomeAssistant,
) -> None:
    """A bicycle route with waypoints keeps the link but reports null ETA."""
    await _setup_integration(hass)

    response = await hass.services.async_call(
        DOMAIN,
        "get_directions",
        {
            "origin": {"latitude": 37.5663, "longitude": 126.9779},
            "waypoints": [{"latitude": 37.53, "longitude": 126.99}],
            "destination": {"latitude": 37.4979, "longitude": 127.0276},
            "mode": "bicycle",
        },
        blocking=True,
        return_response=True,
    )

    assert response["duration"] is None
    assert "경유지1,37.53,126.99" in response["route_url"]


async def test_get_directions_traffic_populates_eta_with_transfers_and_fare(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A transit route fills ETA and adds transfers/fare fields from pubtrans.json."""
    await _setup_integration(hass)
    aioclient_mock.get(TRANSCOORD_URL, json={"documents": [{"x": 495119, "y": 1129657}]})
    aioclient_mock.get(
        PUBTRANS_ROUTE_URL,
        json={
            "in_local_status": "SUCCESS",
            "in_local": {
                "routes": [
                    {
                        "time": {"value": 2949},
                        "distance": {"value": 21607},
                        "fare": {"value": 1650},
                        "transfers": 1,
                    }
                ]
            },
        },
    )

    response = await hass.services.async_call(
        DOMAIN,
        "get_directions",
        {
            "origin": {"latitude": 37.5663, "longitude": 126.9779},
            "destination": {"latitude": 37.4979, "longitude": 127.0276},
            "mode": "traffic",
        },
        blocking=True,
        return_response=True,
    )

    assert response["duration"] == 2949
    assert response["distance"] == 21607
    assert response["transfers"] == 1
    assert response["fare"] == 1650


async def test_get_directions_traffic_degrades_but_keeps_link(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """When transcoord fails, transit ETA is null and no transfers/fare are added."""
    await _setup_integration(hass)
    aioclient_mock.get(TRANSCOORD_URL, status=500)

    response = await hass.services.async_call(
        DOMAIN,
        "get_directions",
        {
            "origin": {"latitude": 37.5663, "longitude": 126.9779},
            "destination": {"latitude": 37.4979, "longitude": 127.0276},
            "mode": "traffic",
        },
        blocking=True,
        return_response=True,
    )

    assert response["duration"] is None
    assert "transfers" not in response
    assert response["route_url"].startswith("https://map.kakao.com/link/by/traffic/")


async def test_get_directions_walk_is_link_only(hass: HomeAssistant) -> None:
    """Walk mode returns the link with null ETA and makes no internal API call.

    walkset.json's contract is unresolved (Open Q2), so walk is intentionally
    link-only. Registering no HTTP mock proves no route lookup is attempted.
    """
    await _setup_integration(hass)

    response = await hass.services.async_call(
        DOMAIN,
        "get_directions",
        {
            "origin": {"latitude": 37.5663, "longitude": 126.9779},
            "destination": {"latitude": 37.5636, "longitude": 126.9850},
            "mode": "walk",
        },
        blocking=True,
        return_response=True,
    )

    assert response["duration"] is None
    assert response["distance"] is None
    assert response["arrival_time"] is None
    assert response["route_url"].startswith("https://map.kakao.com/link/by/walk/")


async def test_get_directions_removed_on_unload(hass: HomeAssistant) -> None:
    """Unloading the entry removes the get_directions service."""
    entry = await _setup_integration(hass)
    assert hass.services.has_service(DOMAIN, "get_directions")

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.services.has_service(DOMAIN, "get_directions")
