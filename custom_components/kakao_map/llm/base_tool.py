"""Base tool class for kakao_map LLM tools."""

from __future__ import annotations

from typing import Any, cast

from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm

from custom_components.kakao_map.api import KakaoLocalApi, KakaoMapRouteApi
from custom_components.kakao_map.const import DOMAIN

from .const import SOURCE


class BaseKakaoTool(llm.Tool):
    """Reads its bound config entry's API clients via hass.data."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        super().__init__()
        self.hass = hass
        self.entry_id = entry_id

    @property
    def store(self) -> dict[str, Any]:
        return cast(
            "dict[str, Any]", self.hass.data.get(DOMAIN, {}).get(self.entry_id, {})
        )

    @property
    def api(self) -> KakaoLocalApi:
        return cast(KakaoLocalApi, self.store["api"])

    @property
    def route_api(self) -> KakaoMapRouteApi:
        return cast(KakaoMapRouteApi, self.store["route_api"])

    def envelope(self, **fields: Any) -> dict[str, Any]:
        """Build a standard response envelope."""
        out: dict[str, Any] = {"source": SOURCE}
        out.update(fields)
        return out
