"""Tests for the Kakao Map config flow."""

from __future__ import annotations

import aiohttp
from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.kakao_map.const import DOMAIN, KEYWORD_SEARCH_URL
from tests.vendor.aiohttp_mock import AiohttpClientMocker
from tests.vendor.ha_common import MockConfigEntry


async def test_user_flow_creates_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A valid API key passes validation and creates the config entry."""
    aioclient_mock.get(KEYWORD_SEARCH_URL, json={"documents": []})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "valid-key"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Kakao Map"
    assert result["data"] == {CONF_API_KEY: "valid-key"}
    assert aioclient_mock.mock_calls[0][3]["Authorization"] == "KakaoAK valid-key"


async def test_user_flow_invalid_auth_then_recovers(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A rejected key (401) shows invalid_auth and the form accepts a retry."""
    aioclient_mock.get(KEYWORD_SEARCH_URL, status=401)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "bad-key"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    aioclient_mock.clear_requests()
    aioclient_mock.get(KEYWORD_SEARCH_URL, json={"documents": []})

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "good-key"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_API_KEY: "good-key"}


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """A network failure during validation shows cannot_connect."""
    aioclient_mock.get(KEYWORD_SEARCH_URL, exc=aiohttp.ClientError("boom"))

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "any-key"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_aborts_when_already_configured(hass: HomeAssistant) -> None:
    """Only a single Kakao Map entry is allowed."""
    MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "key"}, unique_id=DOMAIN).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
