"""get_directions LLM tool."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm

from custom_components.kakao_map.const import DIRECTIONS_MODES, MODE_CAR
from custom_components.kakao_map.services import (
    ATTR_DESTINATION,
    ATTR_MODE,
    ATTR_ORIGIN,
    ATTR_WAYPOINTS,
    async_get_directions,
)

from .base_tool import BaseKakaoTool
from .schema import POINT_INPUT


class GetDirectionsTool(BaseKakaoTool):
    """Build a Kakao Map route between two points, with optional waypoints."""

    name = "get_directions"
    description = (
        "Get a Kakao Map route between an origin and destination (each an "
        "entity_id or a latitude/longitude), with optional ordered "
        "waypoints (max 5). Returns a route link and, when the best-effort "
        "lookup succeeds, duration/distance/arrival_time (plus transfers/"
        "fare for public transit)."
    )
    parameters = vol.Schema(
        {
            vol.Required("origin"): POINT_INPUT,
            vol.Required("destination"): POINT_INPUT,
            vol.Optional("waypoints"): [POINT_INPUT],
            vol.Optional("mode"): vol.In(DIRECTIONS_MODES),
        }
    )

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> dict[str, Any]:
        args = tool_input.tool_args
        data = {
            ATTR_ORIGIN: args.get("origin"),
            ATTR_DESTINATION: args.get("destination"),
            ATTR_WAYPOINTS: args.get("waypoints") or [],
            ATTR_MODE: args.get("mode") or MODE_CAR,
        }
        response = await async_get_directions(hass, self.route_api, data)
        return self.envelope(
            **response,
            instruction=(
                "Mention duration and distance if they aren't null; "
                "otherwise say only the route link is available (the "
                "best-effort ETA lookup failed)."
            ),
        )
