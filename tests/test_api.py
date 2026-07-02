"""Tests for the internal Kakao Map route API client (best-effort ETA)."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.kakao_map.api import KakaoMapRouteApi
from custom_components.kakao_map.const import CARS_ROUTE_URL
from custom_components.kakao_map.helpers import ResolvedPoint

ORIGIN = ResolvedPoint(name="출발지", latitude=37.5663, longitude=126.9779)
DESTINATION = ResolvedPoint(name="도착지", latitude=37.4979, longitude=127.0276)
WAYPOINT = ResolvedPoint(name="경유지1", latitude=37.53, longitude=126.99)

CARS_SUCCESS = [
    {"resultCode": "SUCCESS", "summary": {"duration": 1195, "distance": 10109}}
]


def _route_api(hass: HomeAssistant) -> KakaoMapRouteApi:
    return KakaoMapRouteApi(async_get_clientsession(hass))


async def test_car_route_parses_duration_and_distance(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A SUCCESS response yields duration (s) and distance (m)."""
    aioclient_mock.get(CARS_ROUTE_URL, json=CARS_SUCCESS)

    result = await _route_api(hass).async_get_car_route(ORIGIN, DESTINATION, [])

    assert result is not None
    assert result.duration == 1195
    assert result.distance == 10109


async def test_car_route_sends_lng_lat_name_and_waypoints(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Points are sent as `lng,lat,name=…`, waypoints pipe-joined, with route params."""
    aioclient_mock.get(CARS_ROUTE_URL, json=CARS_SUCCESS)

    await _route_api(hass).async_get_car_route(ORIGIN, DESTINATION, [WAYPOINT])

    params = aioclient_mock.mock_calls[-1][1].query
    assert params["origin"] == "126.9779,37.5663,name=출발지"
    assert params["destination"] == "127.0276,37.4979,name=도착지"
    assert params["waypoints"] == "126.99,37.53,name=경유지1"
    assert params["priority"] == "RECOMMEND"
    assert params["roadside"] == "true"

    headers = aioclient_mock.mock_calls[-1][3]
    assert headers["Referer"] == "https://map.kakao.com/"


async def test_car_route_joins_multiple_waypoints_with_pipe(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Multiple waypoints are joined by `|` in order."""
    aioclient_mock.get(CARS_ROUTE_URL, json=CARS_SUCCESS)
    second = ResolvedPoint(name="경유지2", latitude=37.51, longitude=127.01)

    await _route_api(hass).async_get_car_route(ORIGIN, DESTINATION, [WAYPOINT, second])

    params = aioclient_mock.mock_calls[-1][1].query
    assert params["waypoints"] == "126.99,37.53,name=경유지1|127.01,37.51,name=경유지2"


async def test_car_route_error_result_code_degrades_to_none(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A non-SUCCESS resultCode degrades to None."""
    aioclient_mock.get(CARS_ROUTE_URL, json=[{"resultCode": "ERROR"}])

    result = await _route_api(hass).async_get_car_route(ORIGIN, DESTINATION, [])

    assert result is None


async def test_car_route_http_error_degrades_to_none(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """An HTTP error degrades to None."""
    aioclient_mock.get(CARS_ROUTE_URL, status=500)

    result = await _route_api(hass).async_get_car_route(ORIGIN, DESTINATION, [])

    assert result is None


async def test_car_route_timeout_degrades_to_none(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A timeout degrades to None."""
    aioclient_mock.get(CARS_ROUTE_URL, exc=TimeoutError())

    result = await _route_api(hass).async_get_car_route(ORIGIN, DESTINATION, [])

    assert result is None
