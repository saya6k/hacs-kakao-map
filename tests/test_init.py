"""Smoke tests proving the kakao_map integration loads under HA."""

from __future__ import annotations

from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from custom_components.kakao_map.const import DOMAIN
from tests.vendor.ha_common import MockConfigEntry


async def test_integration_manifest_loads(hass: HomeAssistant) -> None:
    """HA discovers the custom integration and parses a valid manifest."""
    integration = await async_get_integration(hass, DOMAIN)

    assert integration.domain == DOMAIN
    assert integration.config_flow is True


async def test_setup_entry_stores_domain_data(hass: HomeAssistant) -> None:
    """Setting up a config entry initializes hass.data[DOMAIN]."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "test-key"})
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert DOMAIN in hass.data


async def test_unload_entry_clears_domain_data(hass: HomeAssistant) -> None:
    """Unloading a config entry removes its data from hass.data[DOMAIN]."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "test-key"})
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.entry_id not in hass.data[DOMAIN]
