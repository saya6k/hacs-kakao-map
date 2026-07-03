"""Map Kakao Local API documents to the integration's response schema.

Shared by the services and the LLM tools so both surfaces return identical
place/address shapes.
"""

from __future__ import annotations

from typing import Any

from .const import MAP_LINK_BASE


def place_result(doc: dict[str, Any]) -> dict[str, Any]:
    """Map a Kakao search document to the SPEC response schema."""
    name = doc["place_name"]
    latitude = float(doc["y"])
    longitude = float(doc["x"])
    result = {
        "place_name": name,
        "latitude": latitude,
        "longitude": longitude,
        "address": doc["address_name"],
        "road_address": doc["road_address_name"],
        "place_url": doc["place_url"],
        "map_url": f"{MAP_LINK_BASE}/{name},{latitude},{longitude}",
    }
    # Kakao's detailed taxonomy, present on place documents (e.g. a polling station
    # shows up as category_name "…> 선거관리위원회" even though it has no group code).
    if doc.get("category_name"):
        result["category_name"] = doc["category_name"]
    if doc.get("category_group_name"):
        result["category_group_name"] = doc["category_group_name"]
    # `distance` (meters from the center) is only present on nearby searches.
    if doc.get("distance"):
        result["distance"] = int(doc["distance"])
    return result


def address_result(doc: dict[str, Any]) -> dict[str, Any]:
    """Map a Kakao address document to the geocode_address response schema."""
    address = doc["address_name"]
    latitude = float(doc["y"])
    longitude = float(doc["x"])
    # road_address is null for lots that have no assigned road-name address.
    road_address = doc.get("road_address") or {}
    return {
        "latitude": latitude,
        "longitude": longitude,
        "address": address,
        "road_address": road_address.get("address_name"),
        "zone_no": road_address.get("zone_no") or None,
        "map_url": f"{MAP_LINK_BASE}/{address},{latitude},{longitude}",
    }
