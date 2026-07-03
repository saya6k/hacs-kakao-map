"""Constants for the kakao_map LLM API tools."""

from __future__ import annotations

SOURCE = "kakao_map"

API_NAME = "Kakao Map"

API_PROMPT = (
    "You can use these tools to search places and get directions in Korea via "
    "Kakao Map. Use search_place for a plain keyword search anywhere. Use "
    "search_nearby to search around a specific center point (an entity_id like "
    "a zone/person/device_tracker, or a latitude/longitude), passing exactly "
    "one of category or query. Use geocode_address to convert an address "
    "string to coordinates. Use get_directions for a route between an origin "
    "and destination (each an entity_id or latitude/longitude), with optional "
    "waypoints in order; pick mode 'car', 'traffic' (public transit), 'walk', "
    "or 'bicycle'. duration/distance/arrival_time may be null when the "
    "best-effort route lookup fails — the route_url link is still valid. "
    "Cards are already shown for search/nearby results, so keep narration "
    "brief."
)
