"""Place search LLM tools (search_place, search_nearby)."""

from __future__ import annotations

from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import llm

from custom_components.kakao_map.api import KakaoApiError
from custom_components.kakao_map.const import (
    CATEGORY_CODES,
    DEFAULT_NEARBY_RADIUS,
    DOMAIN,
    MAX_NEARBY_RADIUS,
    MAX_SEARCH_RESULTS,
)
from custom_components.kakao_map.formatters import place_result
from custom_components.kakao_map.helpers import resolve_point
from custom_components.kakao_map.services import NEARBY_CENTER_ROLE

from .base_tool import BaseKakaoTool
from .render import grid_results
from .schema import POINT_INPUT

_PLACE_ACCENT = "#0ea5e9"  # sky-500


def _place_card_items(
    results: list[dict[str, Any]],
) -> list[tuple[str, list[tuple[str, str]], dict[str, Any] | None]]:
    items: list[tuple[str, list[tuple[str, str]], dict[str, Any] | None]] = []
    for r in results:
        lines: list[tuple[str, str]] = [("주소", r.get("road_address") or r["address"])]
        category = r.get("category_group_name") or r.get("category_name")
        if category:
            lines.append(("분류", category))
        if "distance" in r:
            lines.append(("거리", f"{r['distance']}m"))
        extra = {"place_url": r.get("place_url"), "map_url": r.get("map_url")}
        items.append((r["place_name"], lines, extra))
    return items


class SearchPlaceTool(BaseKakaoTool):
    """Keyword search anywhere on Kakao Map (not centered on a point)."""

    name = "search_place"
    description = (
        "Search Kakao Map for places by keyword, anywhere (not centered on a "
        "point). Returns up to 5 matches with coordinates, address, and a "
        "map link."
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
            documents = await self.api.async_search_keyword(query)
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
        results = [place_result(doc) for doc in documents[:MAX_SEARCH_RESULTS]]
        return self.envelope(
            places=results,
            results=grid_results(_place_card_items(results), accent=_PLACE_ACCENT),
            instruction=(
                "Cards with each place are already shown. Narrate briefly — "
                "name and address of the top match or two — don't repeat "
                "every field."
            ),
        )


class SearchNearbyTool(BaseKakaoTool):
    """Category or keyword search within a radius of a center point."""

    name = "search_nearby"
    description = (
        "Search Kakao Map for places of a category or keyword within a "
        "radius of a center point (an entity_id like a zone/person/"
        "device_tracker, or a latitude/longitude). Pass exactly one of "
        "category or query. Returns up to 5 matches ordered by distance."
    )
    parameters = vol.Schema(
        {
            vol.Required("center"): POINT_INPUT,
            vol.Optional("category"): vol.In(CATEGORY_CODES),
            vol.Optional("query"): cv.string,
            vol.Optional("radius"): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=MAX_NEARBY_RADIUS)
            ),
        }
    )

    async def async_call(
        self,
        hass: HomeAssistant,
        tool_input: llm.ToolInput,
        llm_context: llm.LLMContext,
    ) -> dict[str, Any]:
        args = tool_input.tool_args
        category = args.get("category")
        query = args.get("query")
        if bool(category) == bool(query):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="nearby_input"
            )
        center = resolve_point(hass, role=NEARBY_CENTER_ROLE, value=args.get("center"))
        radius = args.get("radius") or DEFAULT_NEARBY_RADIUS
        try:
            if category:
                documents = await self.api.async_search_category(
                    CATEGORY_CODES[category], center.longitude, center.latitude, radius
                )
            else:
                documents = await self.api.async_search_keyword(
                    query, longitude=center.longitude, latitude=center.latitude, radius=radius
                )
        except (KakaoApiError, aiohttp.ClientError, TimeoutError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="api_error"
            ) from err
        if not documents:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_results",
                translation_placeholders={"query": query or category},
            )
        results = [place_result(doc) for doc in documents[:MAX_SEARCH_RESULTS]]
        return self.envelope(
            center={
                "name": center.name,
                "latitude": center.latitude,
                "longitude": center.longitude,
            },
            places=results,
            results=grid_results(_place_card_items(results), accent=_PLACE_ACCENT),
            instruction=(
                "Cards with each nearby place are already shown. Mention "
                "name and distance for the closest match or two, briefly."
            ),
        )
