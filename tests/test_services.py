"""Tests for the kakao_map services and point-input resolution."""

from __future__ import annotations

import pytest
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.kakao_map.const import DOMAIN, KEYWORD_SEARCH_URL
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


async def test_search_place_returns_top_result(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """search_place returns the first document mapped to the SPEC response schema."""
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
        "place_name": "스타벅스 판교점",
        "latitude": 37.3945,
        "longitude": 127.1112,
        "address": "경기 성남시 분당구 삼평동 681",
        "road_address": "경기 성남시 분당구 판교역로 4",
        "place_url": "http://place.map.kakao.com/26338954",
        "map_url": "https://map.kakao.com/link/map/스타벅스 판교점,37.3945,127.1112",
    }
    assert aioclient_mock.mock_calls[-1][3]["Authorization"] == "KakaoAK test-key"


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

    point = resolve_point(hass, role="출발지", entity_id="device_tracker.my_phone")

    assert point == ResolvedPoint(name="내 폰", latitude=37.5665, longitude=126.978)


async def test_resolve_entity_without_coordinates(hass: HomeAssistant) -> None:
    """An entity lacking coordinate attributes raises an error naming the entity."""
    hass.states.async_set("sensor.no_location", "on", {"friendly_name": "센서"})

    with pytest.raises(ServiceValidationError) as err:
        resolve_point(hass, role="출발지", entity_id="sensor.no_location")

    assert err.value.translation_key == "entity_missing_coordinates"
    assert err.value.translation_placeholders == {"entity_id": "sensor.no_location"}


async def test_resolve_entity_not_found(hass: HomeAssistant) -> None:
    """An unknown entity_id raises an error naming the entity."""
    with pytest.raises(ServiceValidationError) as err:
        resolve_point(hass, role="도착지", entity_id="zone.nowhere")

    assert err.value.translation_key == "entity_not_found"
    assert err.value.translation_placeholders == {"entity_id": "zone.nowhere"}


async def test_resolve_coords_list(hass: HomeAssistant) -> None:
    """A [latitude, longitude] list resolves with the role as its name."""
    point = resolve_point(hass, role="출발지", coords=[37.5, 127.0])

    assert point == ResolvedPoint(name="출발지", latitude=37.5, longitude=127.0)


async def test_resolve_coords_coerces_strings(hass: HomeAssistant) -> None:
    """Numeric strings in the coords list are coerced to floats."""
    point = resolve_point(hass, role="도착지", coords=["37.4", "127.1"])

    assert point == ResolvedPoint(name="도착지", latitude=37.4, longitude=127.1)


@pytest.mark.parametrize("coords", [[37.5], [37.5, 127.0, 1.0], ["abc", "127.0"], "37.5,127.0"])
async def test_resolve_coords_invalid(hass: HomeAssistant, coords: object) -> None:
    """Coords that are not a list of exactly two floats raise an error."""
    with pytest.raises(ServiceValidationError) as err:
        resolve_point(hass, role="출발지", coords=coords)

    assert err.value.translation_key == "invalid_coords"
    assert err.value.translation_placeholders["role"] == "출발지"


async def test_resolve_entity_and_coords_conflict(hass: HomeAssistant) -> None:
    """Passing both entity and coords for one point raises an error naming the role."""
    with pytest.raises(ServiceValidationError) as err:
        resolve_point(hass, role="출발지", entity_id="zone.home", coords=[37.5, 127.0])

    assert err.value.translation_key == "point_input_conflict"
    assert err.value.translation_placeholders == {"role": "출발지"}


async def test_resolve_neither_entity_nor_coords(hass: HomeAssistant) -> None:
    """Passing neither entity nor coords raises an error naming the role."""
    with pytest.raises(ServiceValidationError) as err:
        resolve_point(hass, role="도착지")

    assert err.value.translation_key == "point_input_missing"
    assert err.value.translation_placeholders == {"role": "도착지"}


async def test_resolve_waypoint_entity(hass: HomeAssistant) -> None:
    """A waypoint entry holding an entity_id resolves like an entity."""
    hass.states.async_set(
        "zone.office",
        "zoning",
        {"latitude": 37.4, "longitude": 127.1, "friendly_name": "회사"},
    )

    point = resolve_waypoint(hass, "zone.office", index=1)

    assert point == ResolvedPoint(name="회사", latitude=37.4, longitude=127.1)


async def test_resolve_waypoint_coord_string(hass: HomeAssistant) -> None:
    """A waypoint entry holding "lat,lon" resolves with a numbered name."""
    point = resolve_waypoint(hass, "37.39, 127.11", index=2)

    assert point == ResolvedPoint(name="경유지2", latitude=37.39, longitude=127.11)


@pytest.mark.parametrize("value", ["판교역", "37.5", "37.5,abc", ""])
async def test_resolve_waypoint_invalid(hass: HomeAssistant, value: str) -> None:
    """A waypoint entry that is neither an entity_id nor "lat,lon" raises an error."""
    with pytest.raises(ServiceValidationError) as err:
        resolve_waypoint(hass, value, index=1)

    assert err.value.translation_key == "invalid_waypoint"
    assert err.value.translation_placeholders == {"value": value}
