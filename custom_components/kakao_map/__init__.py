"""The Kakao Map integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.llm import async_register_api

from .api import KakaoLocalApi, KakaoMapRouteApi
from .const import DOMAIN
from .llm_registration import KakaoMapAPI
from .services import async_setup_services, async_unload_services


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Kakao Map from a config entry."""
    session = async_get_clientsession(hass)
    api = KakaoLocalApi(session, entry.data[CONF_API_KEY])
    route_api = KakaoMapRouteApi(session, api)
    unregister_llm = async_register_api(hass, KakaoMapAPI(hass))
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "api": api,
        "route_api": route_api,
        "unregister_llm": unregister_llm,
    }
    async_setup_services(hass, api, route_api)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Kakao Map config entry."""
    store = hass.data[DOMAIN].pop(entry.entry_id, None)
    if store is not None:
        store["unregister_llm"]()
    async_unload_services(hass)
    return True
