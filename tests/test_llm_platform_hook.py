"""Tests for the kakao_map `llm/` platform hook (async_get_tools).

Requires HA's new `llm` platform-hook architecture (HA >= 2026.8 — the
2026.8.0b0 beta as of writing; see tasks/plan.md T13/T14). Skipped entirely
when it isn't available, e.g. running the default `scripts/test` against the
stable pin; run `scripts/test-dev` to exercise it for real.
"""

from __future__ import annotations

import pytest

pytest.importorskip("homeassistant.components.llm")

from homeassistant.const import CONF_API_KEY
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers.llm import LLMContext

from custom_components.kakao_map.const import DOMAIN
from custom_components.kakao_map.llm import async_get_tools
from tests.vendor.ha_common import MockConfigEntry


def _llm_context() -> LLMContext:
    return LLMContext(
        platform="test", context=Context(), language="ko", assistant="test", device_id=None
    )


async def _setup_integration(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: "test-key"}, unique_id=DOMAIN)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_async_get_tools_returns_tools_for_kakao_map_api(hass: HomeAssistant) -> None:
    """The hook returns kakao_map's 4 tools + prompt for our own api_id with a loaded entry."""
    await _setup_integration(hass)

    result = async_get_tools(hass, _llm_context(), DOMAIN)

    assert result is not None
    assert {t.name for t in result.tools} == {
        "kakao_map__search_place",
        "kakao_map__search_nearby",
        "kakao_map__geocode_address",
        "kakao_map__get_directions",
    }
    assert result.prompt


async def test_async_get_tools_returns_none_for_other_api_id(hass: HomeAssistant) -> None:
    """The hook opts out for any api_id other than kakao_map's own."""
    await _setup_integration(hass)

    assert async_get_tools(hass, _llm_context(), "assist") is None


async def test_async_get_tools_returns_none_without_a_loaded_entry(hass: HomeAssistant) -> None:
    """The hook returns None when no kakao_map config entry is loaded."""
    assert async_get_tools(hass, _llm_context(), DOMAIN) is None
