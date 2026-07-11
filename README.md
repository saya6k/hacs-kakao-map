# Kakao Map — Home Assistant Integration

[![Built with Claude Code](https://img.shields.io/badge/Built%20with%20Claude%20Code-D97757?style=for-the-badge&logo=claude&logoColor=white)](https://claude.ai/code)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-41BDF5?style=for-the-badge&logo=homeassistant&logoColor=white)](https://www.home-assistant.io/)
[![HACS](https://img.shields.io/badge/HACS-Custom-41BDF5?style=for-the-badge&logo=homeassistantcommunitystore&logoColor=white)](https://hacs.xyz/)
[![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Shell](https://img.shields.io/badge/Shell-4EAA25?style=for-the-badge&logo=gnubash&logoColor=white)](https://www.gnu.org/software/bash/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-FFDD00?style=for-the-badge&logo=buymeacoffee&logoColor=black)](https://buymeacoffee.com/saya6k)

Kakao Map for Home Assistant — **place search**, **nearby search**, and **directions** (Kakao Map link plus best-effort travel time) built on the Kakao Local REST API and Kakao Map's web/internal APIs. For Korean users.

> **Map-tile replacement is not supported.** Patching the HA frontend to serve Kakao tiles is not feasible: Kakao tiles are not Web Mercator (XYZ), so a URL swap yields blank tiles, and the frontend's immutable cache + service worker prevent the patch from taking effect.

## Features

- **`search_place`** — keyword place search, returns the top 5 results with coordinates, addresses, and map links.
- **`search_nearby`** — search around a center point (entity or coordinates) by Kakao category code or keyword, ordered by distance, with a `distance` field on each result.
- **`geocode_address`** — convert an address into WGS84 coordinates, returning the best match with its jibun/road address, postal code, and a map link.
- **`get_directions`** — Kakao Map route link + per-leg points + best-effort travel time / arrival time for car, transit, walk, and bicycle. Points are entities (person / device_tracker / zone / …) or coordinates.
- **Assist / AI tool support** — the same actions are exposed as an LLM tool API for AI-backed conversation agents, with visual result cards.
- **Korean and English** UI translations.

## Installation (HACS)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=saya6k&repository=hacs-kakao-map&category=integration)

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

Search around a center by a category code **or** a keyword (exactly one). Each result includes `distance` (meters).

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

Categories (18 total): `cafe`, `restaurant`, `convenience_store`, `supermarket`, `hospital`, `pharmacy`, `subway_station`, `bank`, `gas_station`, `parking`, `academy`, `school`, `daycare`, `cultural_facility`, `real_estate`, `public_institution`, `tourist_attraction`, `accommodation`. In the UI these show as localized labels (카페, 음식점, …); the Kakao category codes are handled internally.

For places that aren't one of the 18 group categories (e.g. a polling station / 투표소), use `query` instead. Every result carries Kakao's detailed `category_name` (e.g. `"사회,공공기관 > 행정기관 > 선거관리위원회"`) and `category_group_name`, so automations can filter on the fine-grained category.

### `kakao_map.geocode_address`

Convert an address into coordinates. Returns the single best match (raises an error if the address isn't found).

```yaml
action: kakao_map.geocode_address
data:
  query: 경기 성남시 분당구 판교역로 4
response_variable: geo
# geo: latitude / longitude / address(jibun) / road_address / zone_no / map_url
```

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

See `custom_components/kakao_map/services.yaml` for all fields.

## Assist support

The same four actions are also registered as an LLM tool API (`search_place`, `search_nearby`, `geocode_address`, `get_directions`), so an AI-backed Assist pipeline (e.g. Google Generative AI Conversation, OpenAI Conversation) can call them from natural language. Enable it in the conversation agent's options by selecting **Kakao Map** under the exposed LLM APIs. Place and nearby-search results also render as visual cards on cards-capable Assist surfaces (e.g. voice-satellite dashboards).

**Tool exposure requires Home Assistant 2026.8+.** On older Home Assistant the integration installs normally and all four services keep working as YAML calls — only Assist/LLM tool registration is unavailable (selecting Kakao Map as an agent's API exposes no tools there).

MCP clients can also reach the API directly at `/api/mcp/kakao_map` (requires an admin-scoped token), independent of any conversation agent's configured API list.

> Upgrading from an older release and had already selected **Kakao Map** in a conversation agent's exposed APIs? Reselect it — the API's internal id changed to a stable identifier.

## Notes and limitations

- **Travel time is best-effort.** `duration` / `distance` / `arrival_time` are parsed from Kakao Map's undocumented internal route API, which may change or be blocked; on failure those fields degrade to `null` while the route link (`route_url`) is always returned.
- **`mode: walk` is link-only** — the walking route API contract is unresolved, so its ETA fields are `null`.
- **`mode: traffic`** (public transit) does not support waypoints and adds `transfers` and `fare` to the response.
- No APIs that require a separate subscription (e.g. Kakao Mobility) are used.
- **No map-tile replacement** — see the note near the top.

## Development

A devcontainer is provided for testing against a real Home Assistant install. Open the folder in VS Code with the Dev Containers extension and run:

```bash
scripts/develop
```

HA binds port 8123 inside the container, whose hostname is `hacs-kakao-map-dev` so it's distinguishable from any production HA on the host network. Run the lint + test suite with `scripts/test`. See `AGENTS.md` for architecture, API facts, and conventions.

## License

[MIT](LICENSE)
