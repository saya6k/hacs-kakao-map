"""LLM platform hook for the kakao_map integration.

Home Assistant's `llm` integration discovers a `<domain>/llm` platform for
every loaded top-level component and aggregates their tools/prompts (see
`homeassistant.components.llm.async_get_tools`, which drives
`homeassistant.helpers.integration_platform.LazyIntegrationPlatforms` — this
module is only imported the first time an LLM request actually needs it, not
at kakao_map setup). `async_get_tools` is the hook contract; we respond only
to requests for our own stable API id.
"""

from __future__ import annotations

from homeassistant.components.llm import LLMTools
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.llm import LLMContext

from custom_components.kakao_map.const import DOMAIN

from .const import API_PROMPT
from .tools import TOOL_FACTORIES


@callback
def async_get_tools(hass: HomeAssistant, llm_context: LLMContext, api_id: str) -> LLMTools | None:
    """Return kakao_map's tools for the kakao_map API only."""
    if api_id != DOMAIN:
        return None
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if not entries:
        return None
    entry = entries[0]  # single-instance integration
    tools = [factory(hass, entry.entry_id) for factory in TOOL_FACTORIES]
    return LLMTools(tools=tools, prompt=API_PROMPT)
