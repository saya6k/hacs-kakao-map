"""Constants for the Kakao Map integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "kakao_map"

# Display name for the llm.API registration. Kept here (component root) rather
# than in llm/const.py: the API shell (llm_registration.py) must not import
# anything from the llm/ package, or it would defeat HA's lazy platform
# loading (see llm_registration.py's module docstring).
API_NAME: Final = "Kakao Map"

# Official Kakao Local REST API endpoints (require `Authorization: KakaoAK {key}`)
KEYWORD_SEARCH_URL: Final = "https://dapi.kakao.com/v2/local/search/keyword.json"
CATEGORY_SEARCH_URL: Final = "https://dapi.kakao.com/v2/local/search/category.json"
ADDRESS_SEARCH_URL: Final = "https://dapi.kakao.com/v2/local/search/address.json"
TRANSCOORD_URL: Final = "https://dapi.kakao.com/v2/local/geo/transcoord.json"

# Kakao Map web URL scheme (no API key required, returns HTML pages)
MAP_LINK_BASE: Final = "https://map.kakao.com/link/map"
DIRECTIONS_LINK_BASE: Final = "https://map.kakao.com/link/by"

# Kakao Map internal route API (undocumented; needs Referer + browser UA, no API key).
# best-effort only: may change or block without notice, so ETA data degrades to null.
CARS_ROUTE_URL: Final = "https://map.kakao.com/route/cars.json"
BIKESET_ROUTE_URL: Final = "https://map.kakao.com/route/bikeset.json"
PUBTRANS_ROUTE_URL: Final = "https://map.kakao.com/route/pubtrans.json"
ROUTE_API_HEADERS: Final = {
    "Referer": "https://map.kakao.com/",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
}

# Directions travel mode tokens used by the web URL scheme
MODE_CAR: Final = "car"
MODE_TRAFFIC: Final = "traffic"
MODE_WALK: Final = "walk"
MODE_BICYCLE: Final = "bicycle"
DIRECTIONS_MODES: Final = (MODE_CAR, MODE_TRAFFIC, MODE_WALK, MODE_BICYCLE)

MAX_WAYPOINTS: Final = 5
MAX_SEARCH_RESULTS: Final = 5

# Nearby search (search_nearby): center point + category code or keyword within a radius.
DEFAULT_NEARBY_RADIUS: Final = 1000  # meters
MAX_NEARBY_RADIUS: Final = 20000  # Kakao's cap for radius (meters)
# Friendly category slugs exposed to users, mapped to Kakao Local group codes
# (category.json). Users never see the raw codes; the slug is the selector value.
CATEGORY_CODES: Final = {
    "supermarket": "MT1",
    "convenience_store": "CS2",
    "daycare": "PS3",
    "school": "SC4",
    "academy": "AC5",
    "parking": "PK6",
    "gas_station": "OL7",
    "subway_station": "SW8",
    "bank": "BK9",
    "cultural_facility": "CT1",
    "real_estate": "AG2",
    "public_institution": "PO3",
    "tourist_attraction": "AT4",
    "accommodation": "AD5",
    "restaurant": "FD6",
    "cafe": "CE7",
    "hospital": "HP8",
    "pharmacy": "PM9",
}
