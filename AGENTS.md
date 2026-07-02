# Repository agent instructions

Briefs Claude / GPT / other coding agents on the conventions and load-bearing facts of
`kakao_map`. Read this before making changes — it is the architecture + operational brief
for the integration (layout, hard rules, API facts, testing).

## Repository layout

```
ha-kakao-map/
├── custom_components/kakao_map/   ← the HA integration (edit this)
│   ├── __init__.py                ← setup_entry: build API clients, register services
│   ├── config_flow.py             ← REST API key input + validation (single instance)
│   ├── api.py                     ← KakaoLocalApi (official: keyword/category/transcoord)
│   │                                + KakaoMapRouteApi (internal: cars/bikeset/pubtrans)
│   ├── services.py                ← search_place / search_nearby / get_directions handlers
│   ├── helpers.py                 ← resolve_point / resolve_waypoint (entity|coords → point)
│   ├── const.py                   ← URLs, mode/category constants
│   ├── services.yaml              ← service field schemas (UI selectors)
│   ├── translations/{en,ko}.json  ← config/service/selector/exception strings
│   └── manifest.json
├── .devcontainer/                 ← devcontainer.json (Apple Container CLI, not Docker)
├── scripts/{setup,develop,test}
├── docs/{en,ko}/index.md          ← published via Zensical (see zensical.*.toml)
├── .github/workflows/             ← CI: test (ruff+pytest), validate (HACS+hassfest),
│                                     release-drafter, docs
├── hacs.json
└── README.md
```

## Hard rules

1. **No new pip runtime dependencies.** Use only HA's bundled `aiohttp` / `voluptuous`.
   `manifest.json` `requirements` stays `[]`. Adding a dependency is an "Ask first".
2. **Internal route APIs are best-effort.** `duration` / `distance` / `arrival_time` come from
   Kakao Map's undocumented endpoints (cars/bikeset/pubtrans). On any failure, degrade those
   fields to `null` and log a warning — **never fail the service**; `route_url` is always
   returned. Keep this client isolated in `api.py` (`KakaoMapRouteApi`).
3. **Translations live in two files that must stay in sync.** Every user-facing string is a
   `translation_key`; add the same key tree to both `translations/en.json` and `ko.json`.
   `test_translations.py` guards that placeholders are bare identifiers and that the mode
   selector covers all modes.
4. **Do not patch the HA frontend / replace map tiles.** This was tried and dropped: Kakao
   tiles are EPSG:5181 (not Web Mercator XYZ) so a URL swap yields blank tiles, and the
   frontend's immutable cache + service worker block the patch. An in-app Kakao map is only
   viable via an iframe + Kakao JS SDK custom panel (not implemented).
5. **Category input is a friendly slug, never a raw Kakao code.** `search_nearby` accepts
   slugs (`cafe`, `restaurant`, …) validated against `const.CATEGORY_CODES`; the handler maps
   the slug to the Kakao group code (CE7, FD6, …) before calling the API. Users never see codes.
6. **Containers use Apple Container CLI, not Docker.** `container run/exec …`, image
   `python:3-3.14-bookworm`, container name `ha-kakao-map-dev`. Never `docker`.

## API facts

- **Official Local REST API** (`Authorization: KakaoAK {REST_API_KEY}`): `search/keyword.json`
  (add `x`,`y`,`radius`,`sort=distance` for nearby), `search/category.json`
  (`category_group_code` + `x`,`y`,`radius`), `geo/transcoord.json` (WGS84 → WCONGNAMUL).
  401 → `InvalidApiKey`.
- **Internal route APIs** (no key; need `Referer: https://map.kakao.com/` + a browser UA):
  `route/cars.json` (car), `route/bikeset.json` (bicycle), `route/pubtrans.json` (transit).
  bike/transit require WCONGNAMUL coords via `transcoord`. `walk` has no working contract →
  link-only, ETA `null`. transit adds `transfers` / `fare`.
- **Category group codes are a fixed Kakao set of 18** — Kakao does not add them dynamically
  and `category.json` accepts only those. Anything else is a keyword (`query`) search; results
  carry Kakao's detailed `category_name` / `category_group_name` for fine-grained filtering.

## Conventions

- Points (`origin`/`destination`/`waypoints`/`center`) are an `entity_id` (lat/lon attrs) or a
  `{latitude, longitude}` mapping — resolve via `helpers.resolve_point` / `resolve_waypoint`.
- All service responses are `{"results": [...]}` (searches) or a route dict; each place result
  is built by `services._place_result` (adds `category_name`/`category_group_name`/`distance`
  only when present).
- Ruff config: line-length 100, rules `E/F/W/I/UP/B/SIM/RUF/PL/ANN/ASYNC/TID`. `PLR0915`
  (max 50 statements) bites `async_setup_services` — keep large/new handlers module-level and
  bind deps with `functools.partial` rather than nesting them in the setup closure.

## Testing

Development and tests run in the Apple Container CLI devcontainer:

```bash
container exec ha-kakao-map-dev scripts/test      # ruff + pytest (commit gate)
container exec ha-kakao-map-dev scripts/develop   # boots HA on :8123 for live testing
```

Coverage lives in `tests/` (`test_api.py`, `test_services.py`, `test_config_flow.py`,
`test_translations.py`, `test_repo_docs.py`). Mock HTTP with `aioclient_mock`. Follow TDD:
write the failing test first, then the minimum code to pass.

## When in doubt

- ETA missing? That's expected on internal-API failure — confirm `route_url` still returns.
- Adding a user-facing string? Update **both** `en.json` and `ko.json` with the same key.
- `PLR0915` on `services.py`? Move the handler out of `async_setup_services`, register with
  `functools.partial(handler, hass, api)`.
- Anything about map-tile replacement? It is intentionally unsupported — see Hard rule 4.
