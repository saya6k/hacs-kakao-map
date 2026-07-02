"""Service handlers for the Kakao Map integration."""

from __future__ import annotations

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
from .const import DOMAIN, MAP_LINK_BASE

SERVICE_SEARCH_PLACE = "search_place"

ATTR_QUERY = "query"

SEARCH_PLACE_SCHEMA = vol.Schema({vol.Required(ATTR_QUERY): cv.string})


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

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEARCH_PLACE,
        _async_search_place,
        schema=SEARCH_PLACE_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )


@callback
def async_unload_services(hass: HomeAssistant) -> None:
    """Remove the kakao_map services."""
    hass.services.async_remove(DOMAIN, SERVICE_SEARCH_PLACE)
