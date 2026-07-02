"""Constants for the Kakao Map integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "kakao_map"

# Official Kakao Local REST API endpoints (require `Authorization: KakaoAK {key}`)
KEYWORD_SEARCH_URL: Final = "https://dapi.kakao.com/v2/local/search/keyword.json"
ADDRESS_SEARCH_URL: Final = "https://dapi.kakao.com/v2/local/search/address.json"
TRANSCOORD_URL: Final = "https://dapi.kakao.com/v2/local/geo/transcoord.json"

# Kakao Map web URL scheme (no API key required, returns HTML pages)
MAP_LINK_BASE: Final = "https://map.kakao.com/link/map"
DIRECTIONS_LINK_BASE: Final = "https://map.kakao.com/link/by"

# Directions travel mode tokens used by the web URL scheme
MODE_CAR: Final = "car"
MODE_TRAFFIC: Final = "traffic"
MODE_WALK: Final = "walk"
MODE_BICYCLE: Final = "bicycle"
DIRECTIONS_MODES: Final = (MODE_CAR, MODE_TRAFFIC, MODE_WALK, MODE_BICYCLE)

MAX_WAYPOINTS: Final = 5
