"""Service handlers for the Kakao Map integration."""

from __future__ import annotations

from datetime import timedelta
from functools import partial
from itertools import pairwise
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .api import KakaoApiError, KakaoLocalApi, KakaoMapRouteApi, TransitResult
from .const import (
    CATEGORY_CODES,
    DEFAULT_NEARBY_RADIUS,
    DIRECTIONS_LINK_BASE,
    DIRECTIONS_MODES,
    DOMAIN,
    MAP_LINK_BASE,
    MAX_NEARBY_RADIUS,
    MAX_SEARCH_RESULTS,
    MAX_WAYPOINTS,
    MODE_BICYCLE,
    MODE_CAR,
    MODE_TRAFFIC,
)
from .helpers import resolve_point, resolve_waypoint

SERVICE_SEARCH_PLACE = "search_place"
SERVICE_SEARCH_NEARBY = "search_nearby"
SERVICE_GEOCODE_ADDRESS = "geocode_address"
SERVICE_GET_DIRECTIONS = "get_directions"

ATTR_QUERY = "query"
ATTR_CENTER = "center"
ATTR_CATEGORY = "category"
ATTR_RADIUS = "radius"
ATTR_ORIGIN = "origin"
ATTR_DESTINATION = "destination"
ATTR_WAYPOINTS = "waypoints"
ATTR_MODE = "mode"

NEARBY_CENTER_ROLE = "중심 지점"

SEARCH_PLACE_SCHEMA = vol.Schema({vol.Required(ATTR_QUERY): cv.string})
GEOCODE_ADDRESS_SCHEMA = vol.Schema({vol.Required(ATTR_QUERY): cv.string})

# A point is an entity_id (resolved from its lat/lon attributes) or a location mapping.
POINT_INPUT = vol.Any(cv.entity_id, dict)

SEARCH_NEARBY_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CENTER): POINT_INPUT,
        vol.Optional(ATTR_CATEGORY): vol.In(CATEGORY_CODES),
        vol.Optional(ATTR_QUERY): cv.string,
        vol.Optional(ATTR_RADIUS, default=DEFAULT_NEARBY_RADIUS): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=MAX_NEARBY_RADIUS)
        ),
    }
)

GET_DIRECTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ORIGIN): POINT_INPUT,
        vol.Optional(ATTR_DESTINATION): POINT_INPUT,
        vol.Optional(ATTR_WAYPOINTS, default=list): [POINT_INPUT],
        vol.Optional(ATTR_MODE, default=MODE_CAR): vol.In(DIRECTIONS_MODES),
    }
)


def _place_result(doc: dict[str, Any]) -> dict[str, Any]:
    """Map a Kakao search document to the SPEC response schema."""
    name = doc["place_name"]
    latitude = float(doc["y"])
    longitude = float(doc["x"])
    result = {
        "place_name": name,
        "latitude": latitude,
        "longitude": longitude,
        "address": doc["address_name"],
        "road_address": doc["road_address_name"],
        "place_url": doc["place_url"],
        "map_url": f"{MAP_LINK_BASE}/{name},{latitude},{longitude}",
    }
    # Kakao's detailed taxonomy, present on place documents (e.g. a polling station
    # shows up as category_name "…> 선거관리위원회" even though it has no group code).
    if doc.get("category_name"):
        result["category_name"] = doc["category_name"]
    if doc.get("category_group_name"):
        result["category_group_name"] = doc["category_group_name"]
    # `distance` (meters from the center) is only present on nearby searches.
    if doc.get("distance"):
        result["distance"] = int(doc["distance"])
    return result


def _address_result(doc: dict[str, Any]) -> dict[str, Any]:
    """Map a Kakao address document to the geocode_address response schema."""
    address = doc["address_name"]
    latitude = float(doc["y"])
    longitude = float(doc["x"])
    # road_address is null for lots that have no assigned road-name address.
    road_address = doc.get("road_address") or {}
    return {
        "latitude": latitude,
        "longitude": longitude,
        "address": address,
        "road_address": road_address.get("address_name"),
        "zone_no": road_address.get("zone_no") or None,
        "map_url": f"{MAP_LINK_BASE}/{address},{latitude},{longitude}",
    }


async def _async_geocode_address(
    api: KakaoLocalApi, call: ServiceCall
) -> ServiceResponse:
    """Geocode an address string to the best-match coordinate result."""
    query = call.data[ATTR_QUERY]
    try:
        documents = await api.async_search_address(query)
    except (KakaoApiError, aiohttp.ClientError, TimeoutError) as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="api_error"
        ) from err
    if not documents:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_results",
            translation_placeholders={"query": query},
        )
    return _address_result(documents[0])


async def _async_search_nearby(
    hass: HomeAssistant, api: KakaoLocalApi, call: ServiceCall
) -> ServiceResponse:
    """Search places of a category or keyword around a center point."""
    category = call.data.get(ATTR_CATEGORY)
    query = call.data.get(ATTR_QUERY)
    if bool(category) == bool(query):
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="nearby_input"
        )
    center = resolve_point(hass, role=NEARBY_CENTER_ROLE, value=call.data.get(ATTR_CENTER))
    radius = call.data[ATTR_RADIUS]
    try:
        if category:
            documents = await api.async_search_category(
                CATEGORY_CODES[category], center.longitude, center.latitude, radius
            )
        else:
            documents = await api.async_search_keyword(
                query, longitude=center.longitude, latitude=center.latitude, radius=radius
            )
    except (KakaoApiError, aiohttp.ClientError, TimeoutError) as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="api_error"
        ) from err
    if not documents:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_results",
            translation_placeholders={"query": query or category},
        )
    return {"results": [_place_result(doc) for doc in documents[:MAX_SEARCH_RESULTS]]}


@callback
def async_setup_services(
    hass: HomeAssistant, api: KakaoLocalApi, route_api: KakaoMapRouteApi
) -> None:
    """Register the kakao_map services against the given API clients."""

    async def _async_search_place(call: ServiceCall) -> ServiceResponse:
        query = call.data[ATTR_QUERY]
        try:
            documents = await api.async_search_keyword(query)
        except (KakaoApiError, aiohttp.ClientError, TimeoutError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="api_error"
            ) from err
        if not documents:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_results",
                translation_placeholders={"query": query},
            )
        return {"results": [_place_result(doc) for doc in documents[:MAX_SEARCH_RESULTS]]}

    async def _async_get_directions(call: ServiceCall) -> ServiceResponse:
        mode = call.data[ATTR_MODE]
        waypoints = call.data[ATTR_WAYPOINTS]
        if len(waypoints) > MAX_WAYPOINTS:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="too_many_waypoints",
                translation_placeholders={
                    "count": str(len(waypoints)),
                    "max": str(MAX_WAYPOINTS),
                },
            )
        if mode == MODE_TRAFFIC and waypoints:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="traffic_no_waypoints"
            )
        points = [resolve_point(hass, role="출발지", value=call.data.get(ATTR_ORIGIN))]
        points.extend(
            resolve_waypoint(hass, value, index=index)
            for index, value in enumerate(waypoints, start=1)
        )
        points.append(resolve_point(hass, role="도착지", value=call.data.get(ATTR_DESTINATION)))
        path = "/".join(f"{p.name},{p.latitude},{p.longitude}" for p in points)
        duration: int | None = None
        distance: int | None = None
        arrival_time: str | None = None
        transit: TransitResult | None = None
        if mode == MODE_CAR:
            car = await route_api.async_get_car_route(points[0], points[-1], points[1:-1])
            if car is not None:
                duration, distance = car.duration, car.distance
        elif mode == MODE_BICYCLE and not waypoints:
            # bikeset.json does not model waypoints here, so only direct routes get an ETA.
            bike = await route_api.async_get_bike_route(points[0], points[-1])
            if bike is not None:
                duration, distance = bike.duration, bike.distance
        elif mode == MODE_TRAFFIC:
            transit = await route_api.async_get_transit_route(points[0], points[-1])
            if transit is not None:
                duration, distance = transit.duration, transit.distance
        # MODE_WALK is intentionally omitted: walkset.json's contract is unresolved,
        # so walk stays link-only with null ETA.
        if duration is not None:
            arrival_time = (dt_util.now() + timedelta(seconds=duration)).isoformat()
        legs = [
            {
                "from": a.name,
                "from_latitude": a.latitude,
                "from_longitude": a.longitude,
                "to": b.name,
                "to_latitude": b.latitude,
                "to_longitude": b.longitude,
            }
            for a, b in pairwise(points)
        ]
        response: dict[str, Any] = {
            "route_url": f"{DIRECTIONS_LINK_BASE}/{mode}/{path}",
            "mode": mode,
            "duration": duration,
            "distance": distance,
            "arrival_time": arrival_time,
            "legs": legs,
        }
        if transit is not None:
            response["transfers"] = transit.transfers
            response["fare"] = transit.fare
        return response

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEARCH_PLACE,
        _async_search_place,
        schema=SEARCH_PLACE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SEARCH_NEARBY,
        partial(_async_search_nearby, hass, api),
        schema=SEARCH_NEARBY_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GEOCODE_ADDRESS,
        partial(_async_geocode_address, api),
        schema=GEOCODE_ADDRESS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_DIRECTIONS,
        _async_get_directions,
        schema=GET_DIRECTIONS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )


@callback
def async_unload_services(hass: HomeAssistant) -> None:
    """Remove the kakao_map services."""
    hass.services.async_remove(DOMAIN, SERVICE_SEARCH_PLACE)
    hass.services.async_remove(DOMAIN, SERVICE_SEARCH_NEARBY)
    hass.services.async_remove(DOMAIN, SERVICE_GEOCODE_ADDRESS)
    hass.services.async_remove(DOMAIN, SERVICE_GET_DIRECTIONS)
