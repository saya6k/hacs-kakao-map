# Kakao Map — Home Assistant Integration

> Source of truth — see [한국어](../ko/index.md) for the Korean translation (may lag).

Kakao Map for Home Assistant — **place search**, **nearby search**, and **directions** (Kakao Map link plus best-effort travel time) built on the Kakao Local REST API and Kakao Map's web/internal APIs. For Korean users.

> **Map-tile replacement is not supported.** Patching the HA frontend to serve Kakao tiles is not feasible: Kakao tiles are not Web Mercator (XYZ), so a URL swap yields blank tiles, and the frontend's immutable cache + service worker prevent the patch from taking effect.

## Features

- **`search_place`** — keyword place search, returns the top 5 results with coordinates, addresses, and map links.
- **`search_nearby`** — search around a center point (entity or coordinates) by category or keyword, ordered by distance, with a `distance` field on each result.
- **`get_directions`** — Kakao Map route link + per-leg points + best-effort travel time / arrival time for car, transit, walk, and bicycle. Points are entities (person / device_tracker / zone / …) or coordinates.
- **Korean and English** UI translations.

## Installation (HACS)

1. HACS → Integrations → ⋮ → **Custom repositories** — add this repo URL with category **Integration**.
2. Install **Kakao Map**.
3. Restart Home Assistant.
4. Settings → Devices & Services → **Add integration** → search "Kakao Map".
5. Enter your Kakao **REST API key** (Kakao Developers → My Application → App Keys → REST API key). The key is validated with a single keyword-search call.

## Manual installation

Copy `custom_components/kakao_map/` into your HA config's `custom_components/` folder and restart.

## Configuration

The config flow takes a single **Kakao REST API key** ([Kakao Developers](https://developers.kakao.com)). Only one entry is supported.

## Services

Every service returns a response, so capture it with `response_variable`.

### `kakao_map.search_place`

```yaml
action: kakao_map.search_place
data:
  query: 카카오판교아지트
response_variable: found
# found.results[]: place_name / latitude / longitude / address / road_address /
#                  place_url / map_url / category_name / category_group_name
```

### `kakao_map.search_nearby`

Search around a center by a category **or** a keyword (exactly one). Each result includes `distance` (meters).

```yaml
# Cafes within 1 km of home
action: kakao_map.search_nearby
data:
  center: zone.home
  category: cafe       # pick from the list below
  radius: 1000
response_variable: cafes
```

```yaml
# Keyword search around coordinates
action: kakao_map.search_nearby
data:
  center:
    latitude: 37.5665
    longitude: 126.978
  query: 스타벅스
  radius: 500
response_variable: nearby
```

Categories (18 total): `cafe`, `restaurant`, `convenience_store`, `supermarket`, `hospital`, `pharmacy`, `subway_station`, `bank`, `gas_station`, `parking`, `academy`, `school`, `daycare`, `cultural_facility`, `real_estate`, `public_institution`, `tourist_attraction`, `accommodation`. In the UI these show as localized labels; the Kakao category codes are handled internally.

For places that aren't one of the 18 group categories (e.g. a polling station / 투표소), use `query` instead. Every result carries Kakao's detailed `category_name` (e.g. `"사회,공공기관 > 행정기관 > 선거관리위원회"`) and `category_group_name`, so automations can filter on the fine-grained category.

### `kakao_map.get_directions`

```yaml
action: kakao_map.get_directions
data:
  origin: person.me                 # an entity …
  destination:                      # … or coordinates
    latitude: 37.3945
    longitude: 127.1112
  waypoints:                        # optional, up to 5
    - zone.office
  mode: car                         # car | traffic | walk | bicycle
response_variable: route
# route: route_url / mode / duration(s) / distance(m) / arrival_time / legs[]
```

## Notes and limitations

- **Travel time is best-effort.** `duration` / `distance` / `arrival_time` are parsed from Kakao Map's undocumented internal route API, which may change or be blocked; on failure those fields degrade to `null` while the route link (`route_url`) is always returned.
- **`mode: walk` is link-only** — the walking route API contract is unresolved, so its ETA fields are `null`.
- **`mode: traffic`** (public transit) does not support waypoints and adds `transfers` and `fare` to the response.
- No APIs that require a separate subscription (e.g. Kakao Mobility) are used.
- **No map-tile replacement** — see the note at the top.
