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

# Frontend map-tile patching (experimental, Open Q1). HA's default basemap is a Leaflet
# raster layer served from cartocdn; patch_map swaps the tile-URL template for Kakao's.
# These strings are the single knob — the Kakao template/projection is provisional until
# verified against a real frontend bundle in T11.
FRONTEND_SUBDIRS: Final = ("frontend_latest", "frontend_es5")
FRONTEND_TILE_MARKER: Final = "basemaps.cartocdn.com"
CARTOCDN_TILE_URL: Final = "https://basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
KAKAO_TILE_URL: Final = "https://map.daumcdn.net/map_2d_hd/{z}/{x}/{y}.png"
FRONTEND_BACKUP_SUFFIX: Final = ".backup"
