"""geocode_address LLM tool."""

from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import llm

from custom_components.kakao_map.api import KakaoApiError
from custom_components.kakao_map.const import DOMAIN
from custom_components.kakao_map.formatters import address_result

from .base_tool import BaseKakaoTool
from .render import svg_card

_GEOCODE_ACCENT = "#a855f7"  # purple-500


class GeocodeAddressTool(BaseKakaoTool):
    """Convert an address string to WGS84 coordinates."""

    name = "geocode_address"
    description = (
        "Convert a Korean address string to WGS84 coordinates, returning "
        "the best-match result's lot/road address, postal code, and a map "
        "link."
    )
    parameters = vol.Schema({vol.Required("query"): cv.string})

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> dict[str, Any]:
        query = tool_input.tool_args["query"]
        try:
            documents = await self.api.async_search_address(query)
        except (KakaoApiError, aiohttp.ClientError, TimeoutError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="api_error"
            ) from err
        if not documents:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_results",
                translation_placeholders={"query": query},
            )
        result = address_result(documents[0])
        card = svg_card(
            result["address"],
            [
                ("도로명", result.get("road_address") or "-"),
                ("우편번호", result.get("zone_no") or "-"),
            ],
            accent=_GEOCODE_ACCENT,
        )
        return self.envelope(
            **result,
            featured_image=card,
            instruction="A card with the address is already shown; confirm it briefly.",
        )
