"""The Kakao Map integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import KakaoLocalApi
from .const import DOMAIN
from .services import async_setup_services, async_unload_services


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Kakao Map from a config entry."""
    api = KakaoLocalApi(async_get_clientsession(hass), entry.data[CONF_API_KEY])
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = api
    async_setup_services(hass, api)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Kakao Map config entry."""
    hass.data[DOMAIN].pop(entry.entry_id, None)
    async_unload_services(hass)
    return True
