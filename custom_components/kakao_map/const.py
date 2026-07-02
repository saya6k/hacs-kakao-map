"""Constants for the Kakao Map integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "kakao_map"

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
# Kakao Local category group codes accepted by category.json.
CATEGORY_GROUP_CODES: Final = (
    "MT1",  # 대형마트
    "CS2",  # 편의점
    "PS3",  # 어린이집·유치원
    "SC4",  # 학교
    "AC5",  # 학원
    "PK6",  # 주차장
    "OL7",  # 주유소·충전소
    "SW8",  # 지하철역
    "BK9",  # 은행
    "CT1",  # 문화시설
    "AG2",  # 중개업소
    "PO3",  # 공공기관
    "AT4",  # 관광명소
    "AD5",  # 숙박
    "FD6",  # 음식점
    "CE7",  # 카페
    "HP8",  # 병원
    "PM9",  # 약국
)
