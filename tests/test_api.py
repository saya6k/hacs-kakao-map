"""Tests for the internal Kakao Map route API client (best-effort ETA)."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.kakao_map.api import KakaoLocalApi, KakaoMapRouteApi
from custom_components.kakao_map.const import (
    ADDRESS_SEARCH_URL,
    BIKESET_ROUTE_URL,
    CARS_ROUTE_URL,
    CATEGORY_SEARCH_URL,
    KEYWORD_SEARCH_URL,
    PUBTRANS_ROUTE_URL,
    TRANSCOORD_URL,
)
from custom_components.kakao_map.helpers import ResolvedPoint
from tests.vendor.aiohttp_mock import AiohttpClientMocker, AiohttpClientMockResponse


async def test_search_category_sends_location_and_returns_documents(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Category search posts the code + center + radius and returns raw documents."""
    api = KakaoLocalApi(async_get_clientsession(hass), "test-key")
    aioclient_mock.get(CATEGORY_SEARCH_URL, json={"documents": [{"place_name": "GS25 시청점"}]})

    docs = await api.async_search_category("CS2", 126.9779, 37.5663, 500)

    assert docs == [{"place_name": "GS25 시청점"}]
    query = aioclient_mock.mock_calls[-1][1].query
    assert query["category_group_code"] == "CS2"
    assert query["x"] == "126.9779"
    assert query["y"] == "37.5663"
    assert query["radius"] == "500"
    assert query["sort"] == "distance"
    assert aioclient_mock.mock_calls[-1][3]["Authorization"] == "KakaoAK test-key"


async def test_search_keyword_with_location_bias(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Keyword search adds x/y/radius/sort when a center is given."""
    api = KakaoLocalApi(async_get_clientsession(hass), "test-key")
    aioclient_mock.get(KEYWORD_SEARCH_URL, json={"documents": []})

    await api.async_search_keyword(
        "스타벅스", longitude=126.9779, latitude=37.5663, radius=800
    )

    query = aioclient_mock.mock_calls[-1][1].query
    assert query["query"] == "스타벅스"
    assert query["x"] == "126.9779"
    assert query["y"] == "37.5663"
    assert query["radius"] == "800"
    assert query["sort"] == "distance"


async def test_search_keyword_without_location_omits_bias(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Plain keyword search sends only the query (no location params)."""
    api = KakaoLocalApi(async_get_clientsession(hass), "test-key")
    aioclient_mock.get(KEYWORD_SEARCH_URL, json={"documents": []})

    await api.async_search_keyword("스타벅스")

    query = aioclient_mock.mock_calls[-1][1].query
    assert "x" not in query
    assert "sort" not in query

async def test_search_address_sends_query_and_returns_documents(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Address search sends the query and returns raw documents with the API key."""
    api = KakaoLocalApi(async_get_clientsession(hass), "test-key")
    aioclient_mock.get(ADDRESS_SEARCH_URL, json={"documents": [{"address_name": "판교역로 4"}]})

    docs = await api.async_search_address("판교역로 4")

    assert docs == [{"address_name": "판교역로 4"}]
    query = aioclient_mock.mock_calls[-1][1].query
    assert query["query"] == "판교역로 4"
    assert aioclient_mock.mock_calls[-1][3]["Authorization"] == "KakaoAK test-key"


ORIGIN = ResolvedPoint(name="출발지", latitude=37.5663, longitude=126.9779)
DESTINATION = ResolvedPoint(name="도착지", latitude=37.4979, longitude=127.0276)
WAYPOINT = ResolvedPoint(name="경유지1", latitude=37.53, longitude=126.99)

CARS_SUCCESS = [
    {"resultCode": "SUCCESS", "summary": {"duration": 1195, "distance": 10109}}
]


# WCONGNAMUL conversions of ORIGIN and DESTINATION (from live transcoord).
ORIGIN_WCONG = {"x": 495119, "y": 1129657}
DEST_WCONG = {"x": 506102, "y": 1110679}


def _route_api(hass: HomeAssistant) -> KakaoMapRouteApi:
    local = KakaoLocalApi(async_get_clientsession(hass), "test-key")
    return KakaoMapRouteApi(async_get_clientsession(hass), local)


def _mock_transcoord(aioclient_mock: AiohttpClientMocker) -> None:
    """Return WCONGNAMUL coords keyed by the WGS84 x (longitude) in the request."""

    async def _side_effect(method, url, data):
        lng = url.query["x"]
        doc = ORIGIN_WCONG if lng == str(ORIGIN.longitude) else DEST_WCONG
        return AiohttpClientMockResponse(method, url, json={"documents": [doc]})

    aioclient_mock.get(TRANSCOORD_URL, side_effect=_side_effect)


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


BIKE_SUCCESS = {
    "resultCode": "SUCCESS",
    "directions": [{"time": 3531, "length": 14479}],
}
PUBTRANS_SUCCESS = {
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
}


async def test_transcoord_converts_wgs84_to_wcongnamul(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """transcoord returns the WCONGNAMUL x/y and sends the right params + key."""
    aioclient_mock.get(TRANSCOORD_URL, json={"documents": [ORIGIN_WCONG]})
    api = KakaoLocalApi(async_get_clientsession(hass), "test-key")

    x, y = await api.async_transcoord(126.9779, 37.5663)

    assert (x, y) == (495119, 1129657)
    params = aioclient_mock.mock_calls[-1][1].query
    assert params["x"] == "126.9779"
    assert params["y"] == "37.5663"
    assert params["input_coord"] == "WGS84"
    assert params["output_coord"] == "WCONGNAMUL"
    assert aioclient_mock.mock_calls[-1][3]["Authorization"] == "KakaoAK test-key"


async def test_bike_route_transcoords_then_parses(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A bike route converts both points and reads directions[0].time/length."""
    _mock_transcoord(aioclient_mock)
    aioclient_mock.get(BIKESET_ROUTE_URL, json=BIKE_SUCCESS)

    result = await _route_api(hass).async_get_bike_route(ORIGIN, DESTINATION)

    assert result is not None
    assert result.duration == 3531
    assert result.distance == 14479
    params = aioclient_mock.mock_calls[-1][1].query
    assert (params["sX"], params["sY"]) == ("495119", "1129657")
    assert (params["eX"], params["eY"]) == ("506102", "1110679")


async def test_bike_route_error_result_code_degrades_to_none(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A non-SUCCESS bikeset resultCode degrades to None."""
    _mock_transcoord(aioclient_mock)
    aioclient_mock.get(BIKESET_ROUTE_URL, json={"resultCode": "ERROR"})

    result = await _route_api(hass).async_get_bike_route(ORIGIN, DESTINATION)

    assert result is None


async def test_bike_route_transcoord_failure_degrades_to_none(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A transcoord failure degrades the whole bike lookup to None."""
    aioclient_mock.get(TRANSCOORD_URL, status=500)
    aioclient_mock.get(BIKESET_ROUTE_URL, json=BIKE_SUCCESS)

    result = await _route_api(hass).async_get_bike_route(ORIGIN, DESTINATION)

    assert result is None


async def test_transit_route_parses_time_distance_fare_transfers(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A transit route reads the representative route's nested value fields."""
    _mock_transcoord(aioclient_mock)
    aioclient_mock.get(PUBTRANS_ROUTE_URL, json=PUBTRANS_SUCCESS)

    result = await _route_api(hass).async_get_transit_route(ORIGIN, DESTINATION)

    assert result is not None
    assert result.duration == 2949
    assert result.distance == 21607
    assert result.fare == 1650
    assert result.transfers == 1


async def test_transit_route_error_status_degrades_to_none(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A non-SUCCESS in_local_status degrades to None."""
    _mock_transcoord(aioclient_mock)
    aioclient_mock.get(PUBTRANS_ROUTE_URL, json={"in_local_status": "NO_RESULT"})

    result = await _route_api(hass).async_get_transit_route(ORIGIN, DESTINATION)

    assert result is None
