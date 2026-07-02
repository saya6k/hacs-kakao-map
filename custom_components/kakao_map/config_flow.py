"""Config flow for the Kakao Map integration."""

from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import InvalidApiKey, KakaoLocalApi
from .const import DOMAIN

STEP_USER_SCHEMA = vol.Schema({vol.Required(CONF_API_KEY): str})

# Any keyword works for validating the key; we only care about the HTTP status.
VALIDATION_QUERY = "카카오"


class KakaoMapConfigFlow(ConfigFlow, domain=DOMAIN):
    """Collect and validate the Kakao REST API key."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the API key form."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        errors: dict[str, str] = {}
        if user_input is not None:
            api = KakaoLocalApi(async_get_clientsession(self.hass), user_input[CONF_API_KEY])
            try:
                await api.async_search_keyword(VALIDATION_QUERY)
            except InvalidApiKey:
                errors["base"] = "invalid_auth"
            except (aiohttp.ClientError, TimeoutError):
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title="Kakao Map", data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )
