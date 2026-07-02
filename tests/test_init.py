"""Smoke tests proving the kakao_map integration loads under HA."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from custom_components.kakao_map.const import DOMAIN


async def test_integration_manifest_loads(hass: HomeAssistant) -> None:
    """HA discovers the custom integration and parses a valid manifest."""
    integration = await async_get_integration(hass, DOMAIN)

    assert integration.domain == DOMAIN
    assert integration.config_flow is True
