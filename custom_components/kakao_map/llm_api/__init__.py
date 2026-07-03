"""LLM API registration for the kakao_map integration.

kakao_map supports a single config entry, so a single llm.API is registered
per entry (unregistered on unload), exposing the search/geocode/directions
tools.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm

from custom_components.kakao_map.const import DOMAIN

from .const import API_NAME, API_PROMPT
from .tools import TOOL_FACTORIES, ToolFactory

_LOGGER = logging.getLogger(__name__)


def _api_id(entry_id: str) -> str:
    return f"{DOMAIN}__{entry_id}"


class _KakaoMapAPI(llm.API):
    """An llm.API exposing the kakao_map tools bound to one config entry."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        tool_factories: list[ToolFactory],
    ) -> None:
        super().__init__(hass=hass, id=_api_id(entry_id), name=API_NAME)
        self._entry_id = entry_id
        self._tool_factories = tool_factories

    async def async_get_api_instance(self, llm_context: llm.LLMContext) -> llm.APIInstance:
        tools = [factory(self.hass, self._entry_id) for factory in self._tool_factories]
        return llm.APIInstance(
            api=self, api_prompt=API_PROMPT, llm_context=llm_context, tools=tools
        )


async def async_setup_llm_api(
    hass: HomeAssistant, entry: ConfigEntry
) -> Callable[[], None] | None:
    """Register an llm.API for this entry.

    Returns the unregister callable (caller stores it for unload).
    """
    api = _KakaoMapAPI(hass, entry.entry_id, TOOL_FACTORIES)
    unreg = llm.async_register_api(hass, api)
    _LOGGER.info("Registered LLM API %s", api.id)
    return unreg


def async_cleanup_llm_api(unregister: Callable[[], None] | None) -> None:
    """Invoke the unregister callable returned by async_setup_llm_api."""
    if unregister is None:
        return
    try:
        unregister()
    except Exception as e:  # pragma: no cover
        _LOGGER.debug("Error unregistering LLM API: %s", e)


__all__ = [
    "async_cleanup_llm_api",
    "async_setup_llm_api",
]
