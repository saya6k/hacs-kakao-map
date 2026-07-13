"""Tests for the kakao_map llm.API shell (KakaoMapAPI) and its tools.

Requires HA's new `llm` platform-hook architecture — see
tests/test_llm_platform_hook.py's module docstring for the same caveat.
"""

from __future__ import annotations

import pytest

pytest.importorskip("homeassistant.components.llm")

from homeassistant.const import CONF_API_KEY
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import llm
from homeassistant.setup import async_setup_component

from custom_components.kakao_map.const import (
    ADDRESS_SEARCH_URL,
    CARS_ROUTE_URL,
    CATEGORY_SEARCH_URL,
    DOMAIN,
    KEYWORD_SEARCH_URL,
)
from tests.vendor.aiohttp_mock import AiohttpClientMocker
from tests.vendor.ha_common import MockConfigEntry

STARBUCKS_DOC = {
    "place_name": "스타벅스 판교점",
    "x": "127.1112",
    "y": "37.3945",
    "address_name": "경기 성남시 분당구 삼평동 681",
    "road_address_name": "경기 성남시 분당구 판교역로 4",
    "place_url": "http://place.map.kakao.com/26338954",
}

ADDRESS_DOC = {
    "address_name": "경기 성남시 분당구 삼평동 681",
    "x": "127.1112",
    "y": "37.3945",
    "road_address": {
        "address_name": "경기 성남시 분당구 판교역로 4",
        "zone_no": "13529",
    },
}


async def _setup_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the `llm` integration plus a kakao_map config entry."""
    await async_setup_component(hass, "llm", {})
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "test-key"}, unique_id=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _llm_context() -> llm.LLMContext:
    return llm.LLMContext(
        platform="test", context=Context(), language="ko", assistant="test", device_id=None
    )


async def _get_api_instance(hass: HomeAssistant) -> llm.APIInstance:
    api = next(a for a in llm.async_get_apis(hass) if a.id == DOMAIN)
    return await api.async_get_api_instance(_llm_context())


async def test_llm_api_registered_with_stable_id(hass: HomeAssistant) -> None:
    """Setting up the entry registers a KakaoMapAPI under the stable "kakao_map" id."""
    await _setup_integration(hass)

    assert any(a.id == DOMAIN for a in llm.async_get_apis(hass))


async def test_llm_api_instance_has_four_tools_plus_get_date_time(hass: HomeAssistant) -> None:
    """The aggregated instance has kakao_map's 4 tools plus the llm integration's GetDateTime."""
    await _setup_integration(hass)

    instance = await _get_api_instance(hass)

    assert {t.name for t in instance.tools} == {
        "search_place",
        "search_nearby",
        "geocode_address",
        "get_directions",
        "GetDateTime",
    }
    assert instance.api_prompt


async def test_llm_api_unregistered_on_unload(hass: HomeAssistant) -> None:
    """Unloading the entry unregisters the KakaoMapAPI."""
    entry = await _setup_integration(hass)
    assert any(a.id == DOMAIN for a in llm.async_get_apis(hass))

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert not any(a.id == DOMAIN for a in llm.async_get_apis(hass))


async def test_search_place_tool_returns_places_and_cards(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """search_place returns the formatted place list plus one card per result."""
    await _setup_integration(hass)
    aioclient_mock.get(KEYWORD_SEARCH_URL, json={"documents": [STARBUCKS_DOC]})
    instance = await _get_api_instance(hass)

    result = await instance.async_call_tool(
        llm.ToolInput(tool_name="search_place", tool_args={"query": "판교 스타벅스"})
    )

    assert result["source"] == "kakao_map"
    assert result["places"][0]["place_name"] == "스타벅스 판교점"
    assert len(result["results"]) == 1
    assert result["results"][0]["title"] == "스타벅스 판교점"
    assert result["results"][0]["image_url"].startswith("data:image/svg+xml;base64,")


async def test_search_place_tool_no_results(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """search_place raises a validation error when nothing matches."""
    await _setup_integration(hass)
    aioclient_mock.get(KEYWORD_SEARCH_URL, json={"documents": []})
    instance = await _get_api_instance(hass)

    with pytest.raises(ServiceValidationError) as err:
        await instance.async_call_tool(
            llm.ToolInput(tool_name="search_place", tool_args={"query": "존재하지않는장소"})
        )

    assert err.value.translation_key == "no_results"


async def test_search_nearby_tool_by_category(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """search_nearby resolves an entity center and searches by category."""
    await _setup_integration(hass)
    hass.states.async_set(
        "zone.home", "zoning", {"latitude": 37.5663, "longitude": 126.9779, "friendly_name": "집"}
    )
    doc = {**STARBUCKS_DOC, "place_name": "GS25 시청점", "distance": "120"}
    aioclient_mock.get(CATEGORY_SEARCH_URL, json={"documents": [doc]})
    instance = await _get_api_instance(hass)

    result = await instance.async_call_tool(
        llm.ToolInput(
            tool_name="search_nearby",
            tool_args={"center": "zone.home", "category": "convenience_store", "radius": 500},
        )
    )

    assert result["places"][0]["place_name"] == "GS25 시청점"
    assert result["places"][0]["distance"] == 120
    assert result["center"]["name"] == "집"


async def test_search_nearby_tool_requires_exactly_one_of_category_or_query(
    hass: HomeAssistant,
) -> None:
    """search_nearby rejects a call with neither (or both) category and query."""
    await _setup_integration(hass)
    instance = await _get_api_instance(hass)

    with pytest.raises(ServiceValidationError) as err:
        await instance.async_call_tool(
            llm.ToolInput(
                tool_name="search_nearby",
                tool_args={"center": {"latitude": 37.5, "longitude": 127.0}},
            )
        )

    assert err.value.translation_key == "nearby_input"


async def test_geocode_address_tool_returns_result_and_card(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """geocode_address returns the best-match coordinate result plus a card."""
    await _setup_integration(hass)
    aioclient_mock.get(ADDRESS_SEARCH_URL, json={"documents": [ADDRESS_DOC]})
    instance = await _get_api_instance(hass)

    result = await instance.async_call_tool(
        llm.ToolInput(tool_name="geocode_address", tool_args={"query": "판교역로 4"})
    )

    assert result["latitude"] == 37.3945
    assert result["road_address"] == "경기 성남시 분당구 판교역로 4"
    assert result["featured_image"].startswith("data:image/svg+xml;base64,")


async def test_get_directions_tool_builds_route(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """get_directions resolves coordinate points and returns the route link."""
    await _setup_integration(hass)
    aioclient_mock.get(CARS_ROUTE_URL, status=500)
    instance = await _get_api_instance(hass)

    result = await instance.async_call_tool(
        llm.ToolInput(
            tool_name="get_directions",
            tool_args={
                "origin": {"latitude": 37.5, "longitude": 127.0},
                "destination": {"latitude": 37.4, "longitude": 127.1},
            },
        )
    )

    assert result["mode"] == "car"
    assert result["duration"] is None
    assert result["route_url"] == (
        "https://map.kakao.com/link/by/car/출발지,37.5,127.0/도착지,37.4,127.1"
    )


async def test_get_directions_tool_rejects_too_many_waypoints(hass: HomeAssistant) -> None:
    """get_directions raises a validation error for more than 5 waypoints."""
    await _setup_integration(hass)
    instance = await _get_api_instance(hass)

    with pytest.raises(ServiceValidationError) as err:
        await instance.async_call_tool(
            llm.ToolInput(
                tool_name="get_directions",
                tool_args={
                    "origin": {"latitude": 37.5, "longitude": 127.0},
                    "destination": {"latitude": 37.4, "longitude": 127.1},
                    "waypoints": [{"latitude": 37.0 + i, "longitude": 127.0} for i in range(6)],
                },
            )
        )

    assert err.value.translation_key == "too_many_waypoints"
