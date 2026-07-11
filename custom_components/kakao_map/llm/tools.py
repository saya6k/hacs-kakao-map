"""The list of llm.Tool factory callables kakao_map exposes."""

from __future__ import annotations

from collections.abc import Callable

from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm

from .base_tool import BaseKakaoTool
from .directions_tool import GetDirectionsTool
from .geocode_tool import GeocodeAddressTool
from .place_tools import SearchNearbyTool, SearchPlaceTool

ToolFactory = Callable[[HomeAssistant, str], llm.Tool]


def _factory(cls: type[BaseKakaoTool]) -> ToolFactory:
    def make(hass: HomeAssistant, entry_id: str) -> llm.Tool:
        return cls(hass, entry_id)

    return make


TOOL_FACTORIES: list[ToolFactory] = [
    _factory(SearchPlaceTool),
    _factory(SearchNearbyTool),
    _factory(GeocodeAddressTool),
    _factory(GetDirectionsTool),
]
