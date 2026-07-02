"""Service handlers for the Kakao Map integration."""

from __future__ import annotations

from itertools import pairwise

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

from .api import KakaoApiError, KakaoLocalApi
from .const import (
    DIRECTIONS_LINK_BASE,
    DIRECTIONS_MODES,
    DOMAIN,
    MAP_LINK_BASE,
    MAX_WAYPOINTS,
    MODE_CAR,
    MODE_TRAFFIC,
)
from .helpers import resolve_point, resolve_waypoint

SERVICE_SEARCH_PLACE = "search_place"
SERVICE_GET_DIRECTIONS = "get_directions"

ATTR_QUERY = "query"
ATTR_ORIGIN = "origin"
ATTR_DESTINATION = "destination"
ATTR_WAYPOINTS = "waypoints"
ATTR_MODE = "mode"

SEARCH_PLACE_SCHEMA = vol.Schema({vol.Required(ATTR_QUERY): cv.string})

# A point is an entity_id (resolved from its lat/lon attributes) or a location mapping.
POINT_INPUT = vol.Any(cv.entity_id, dict)

GET_DIRECTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ORIGIN): POINT_INPUT,
        vol.Optional(ATTR_DESTINATION): POINT_INPUT,
        vol.Optional(ATTR_WAYPOINTS, default=list): [POINT_INPUT],
        vol.Optional(ATTR_MODE, default=MODE_CAR): vol.In(DIRECTIONS_MODES),
    }
)


@callback
def async_setup_services(hass: HomeAssistant, api: KakaoLocalApi) -> None:
    """Register the kakao_map services against the given API client."""

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
        doc = documents[0]
        name = doc["place_name"]
        latitude = float(doc["y"])
        longitude = float(doc["x"])
        return {
            "place_name": name,
            "latitude": latitude,
            "longitude": longitude,
            "address": doc["address_name"],
            "road_address": doc["road_address_name"],
            "place_url": doc["place_url"],
            "map_url": f"{MAP_LINK_BASE}/{name},{latitude},{longitude}",
        }

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
        return {
            "route_url": f"{DIRECTIONS_LINK_BASE}/{mode}/{path}",
            "mode": mode,
            "duration": None,
            "distance": None,
            "arrival_time": None,
            "legs": legs,
        }

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEARCH_PLACE,
        _async_search_place,
        schema=SEARCH_PLACE_SCHEMA,
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
    hass.services.async_remove(DOMAIN, SERVICE_GET_DIRECTIONS)
