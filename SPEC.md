# Spec: HA Kakao Map (`kakao_map`)

Home Assistant 커스텀 컴포넌트. Kakao Local REST API, 카카오맵 웹 URL 스킴, 카카오맵 내부 경로 API를
이용해 장소 검색·길찾기 서비스를 제공하고, HA 기본 지도 타일을 카카오맵으로 교체(실험적)한다.

## Objective

한국 사용자용 HA 통합. 세 가지 기능:

1. **장소 검색 서비스** — 자연어 키워드로 장소를 검색해 상위 1건의 좌표·주소·카카오맵 링크를 반환
2. **길찾기 서비스** — 출발/도착/경유지(선택)를 **entity selector(위치 보유 기기/엔티티) 또는 좌표**로 받아,
   이동수단(자동차/대중교통/도보/자전거)별 카카오맵 길찾기 링크 + 구간 리스트 + 소요시간·도착 예정시간을 반환
3. **기본 지도 교체 서비스** — HA 프론트엔드의 기본 지도 타일(cartocdn)을 카카오맵 타일로 패치 (실험적, Open Questions 참조)

### 사용자 결정 사항 (2026-07-02 확정)

- 카카오모빌리티 API 미사용 (별도 가입 필요). 소요시간은 카카오맵 웹 내부 API를 파싱해 획득
- "지도 이미지 링크"는 map.kakao.com 링크로 대체 (카카오는 정적 지도 이미지 REST API 없음)
- 지도 교체는 map_change 방식(프론트엔드 패치)으로 시도, 깨지면 재검토
- `get_directions`의 지점 입력은 **좌표 또는 entity selector** — selector로 받은 기기/엔티티는 좌표로 변환해 길찾기
- 테스트는 devcontainer에서 수행 — `~/Projects/ha-chzzk`, `~/Projects/ha-wardrowbe` 구조 참조
- 컨테이너 빌드/실행은 Docker 대신 **Apple Container CLI**(`container`) 사용
- 사용자 환경: 카카오 REST API 키 보유, HA 2026.x

### API 사실 확인 (2026-07-02 실측 검증 완료)

**공식 API** (`Authorization: KakaoAK {REST_API_KEY}` 헤더):

- `GET https://dapi.kakao.com/v2/local/search/keyword.json` — 키워드 장소 검색.
  `documents[]`: `place_name`, `x`(경도), `y`(위도), `address_name`, `road_address_name`, `place_url`
- `GET https://dapi.kakao.com/v2/local/search/address.json` — 주소 → WGS84 좌표 지오코딩
- `GET https://dapi.kakao.com/v2/local/geo/transcoord.json` — 좌표계 변환.
  WGS84 → WCONGNAMUL 변환에 사용 (내부 경로 API의 좌표 입력용)

**카카오맵 URL 스킴** (공식 문서, 데이터 반환 없음 — 사용자에게 제공할 링크):

- 지도 표시: `https://map.kakao.com/link/map/{이름},{위도},{경도}`
- 길찾기: `https://map.kakao.com/link/by/{mode}/{이름},{위도},{경도}/.../{이름},{위도},{경도}`
  - mode 토큰: `car`, `traffic`(대중교통), `walk`, `bicycle`
  - 경유지 최대 5개, **traffic 모드는 경유지 불가**

**카카오맵 내부 경로 API** (비공개·비문서화 — map.kakao.com 웹이 사용하는 엔드포인트를 실측으로 확인.
공통 헤더 필수: `Referer: https://map.kakao.com/`, 브라우저 User-Agent. API 키 불필요):

| 모드 | 엔드포인트 | 좌표계 | 파라미터 (실측) | 응답 핵심 필드 |
|---|---|---|---|---|
| 자동차 | `GET map.kakao.com/route/cars.json` | **WGS84** | `origin=경도,위도,name={이름}`, `destination=〃`, `waypoints=〃\|〃`, `priority=RECOMMEND`, `roadside=true` | `[0].summary.duration`(초), `.distance`(m), `sections[]` |
| 자전거 | `GET map.kakao.com/route/bikeset.json` | **WCONGNAMUL** | `sX,sY,eX,eY` (+경유지 `pX,pY,u2X,u2Y`) | `directions[].time`(초), `.length`(m), `sections[]` |
| 대중교통 | `GET map.kakao.com/route/pubtrans.json` | **WCONGNAMUL** | `sX,sY,eX,eY` (경유지 불가) | `in_local.routes[].time`, `.fare`, `.transfers`, `summaries` |
| 도보 | `GET map.kakao.com/route/walkset.json` | 미확정 | `sName,eName,sX,sY,eX,eY,pName,pX,pY,u2X,u2Y,ids` 전체 필요(빈 값 허용, 누락 시 302) | HTTP 200 확인, 성공 계약 미확정 — 구현 시 브라우저 devtools로 확정 |

- `origin`/`destination`에 `name=` 성분 누락 시 cars.json이 ERROR 반환 — name 필수
- **리스크**: 내부 API는 예고 없이 변경·차단될 수 있음 (과거 `carset.json` 폐기 확인).
  따라서 소요시간·구간 데이터는 **best-effort**: 실패해도 서비스는 링크를 항상 반환하고
  `duration: null` + 경고 로그로 우아하게 강등

## Tech Stack

- Python ≥ 3.14 (HA 2026.3+가 3.14.2 요구), Home Assistant ≥ 2026.4 custom component
- HTTP: HA 내장 `aiohttp` (`async_get_clientsession`) — 신규 런타임 의존성 없음
- 설정: Config Flow (UI에서 REST API 키 입력, 키워드 검색 1회로 검증)
- 서비스 응답: `SupportsResponse.ONLY`
- 배포: HACS 커스텀 저장소 호환 (`hacs.json`, zip_release: false)
- 개발환경: devcontainer (`mcr.microsoft.com/devcontainers/python:3-3.14-bookworm`,
  ha-xbloom과 동일 패턴), Apple Container CLI로 구동

## Commands

```bash
# devcontainer 기동 (Apple Container CLI — Docker 미사용)
# --rm 금지: stop 시 컨테이너(설치물 포함)가 삭제됨. 메모리 기본 1GB는
# default_config 첫 부팅+pytest 동시 실행 시 스래싱 → 4GB 지정.
container run --name ha-kakao-map-dev -d --memory 4g --cpus 4 \
  -v "$PWD":/workspaces/ha-kakao-map -w /workspaces/ha-kakao-map \
  -p 8123:8123 \
  mcr.microsoft.com/devcontainers/python:3-3.14-bookworm sleep infinity

container exec ha-kakao-map-dev scripts/setup    # HA + 테스트 의존성 설치
container exec ha-kakao-map-dev scripts/test     # ruff + pytest
container exec ha-kakao-map-dev scripts/develop  # HA dev 서버 (호스트 8123 포워딩)

# 컨테이너 내부 개별 실행
pytest tests/ -v
ruff check custom_components/ tests/
```

`scripts/setup`은 wardrowbe 패턴을 따름: HA pip 설치, `config/` 생성,
`config/custom_components/kakao_map` → 저장소 심링크(핫 리로드).

## Project Structure

```
.devcontainer/devcontainer.json   # ha-chzzk/ha-wardrowbe와 동일 패턴 (image, port 8123, postCreateCommand)
scripts/
  setup                # HA + 테스트 의존성 설치, config/ 초기화, 심링크
  develop              # hass --config config/ --debug
  test                 # ruff check + pytest
custom_components/kakao_map/
  __init__.py          # setup_entry: API 클라이언트 생성, 서비스 등록
  manifest.json        # domain: kakao_map, config_flow: true, iot_class: cloud_polling
  config_flow.py       # REST API 키 입력 + 검증
  const.py             # DOMAIN, URL/모드 상수
  api.py               # KakaoLocalApi(공식: keyword/address/transcoord) + KakaoMapRouteApi(내부: cars/bikeset/pubtrans/walkset)
  services.py          # search_place / get_directions / patch_map / restore_map 핸들러
  map_patch.py         # 프론트엔드 타일 URL 패치 로직 (실험적)
  services.yaml
  translations/
    en.json
    ko.json
config/                # devcontainer 전용 HA 런타임 설정 (gitignore, setup이 생성)
tests/
  conftest.py
  requirements_test.txt  # pytest-homeassistant-custom-component>=0.13.300, homeassistant>=2026.4.0
  test_config_flow.py
  test_api.py
  test_services.py
  test_map_patch.py
hacs.json
pyproject.toml         # ruff/mypy/pytest 설정 (wardrowbe 패턴)
SPEC.md
```

## Services

### `kakao_map.search_place`

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `query` | string | O | 검색 키워드 (예: "판교 스타벅스") |

응답 (상위 1건):

```yaml
place_name: 스타벅스 판교점
latitude: 37.39...
longitude: 127.11...
address: 경기 성남시 분당구 ...        # address_name
road_address: 경기 성남시 분당구 ...   # road_address_name
place_url: http://place.map.kakao.com/...
map_url: https://map.kakao.com/link/map/스타벅스 판교점,37.39...,127.11...
```

결과 0건 → `ServiceValidationError`.

### `kakao_map.get_directions`

각 지점(출발/도착)은 **하나의 필드**로 입력하며, 값은 **위치 보유 엔티티(entity_id) 또는
`{latitude, longitude}` 매핑** 중 하나. 엔티티/좌표를 별도 필드로 분리하지 않는다.

| 필드 | 값 | 필수 | 설명 |
|---|---|---|---|
| `origin` | entity_id 또는 `{latitude, longitude}` | O | 출발지 (위치 엔티티 또는 좌표) |
| `destination` | entity_id 또는 `{latitude, longitude}` | O | 도착지 |
| `waypoints` | list — 각 항목 entity_id 또는 `{latitude, longitude}` | X | 경유지 최대 5개 |
| `mode` | select | X | `car`(기본) / `traffic` / `walk` / `bicycle` |

UI selector: `origin`/`destination`은 `entity`(person/device_tracker/zone/geo_location/sensor 등
`latitude`/`longitude` 속성 보유 엔티티), `waypoints`는 `object`. 좌표 매핑은 스키마가 함께 허용
(`vol.Any(cv.entity_id, dict)`)하므로 YAML·템플릿으로 직접 전달 가능.

**위치 해석 규칙:**
1. 값이 문자열(entity_id) → 상태의 `latitude`/`longitude` 속성 사용, 이름은 friendly_name.
   좌표 속성 없으면 `ServiceValidationError` (해당 엔티티 명시)
2. 값이 매핑 `{latitude, longitude}`(radius는 무시) → 좌표 사용, 이름은 "출발지"/"도착지"/"경유지N"
3. 어느 형식도 아니면 `ServiceValidationError` (실패한 지점·값을 메시지에 명시)

**검증:** `mode: traffic` + `waypoints` → 에러 (카카오맵 미지원)

**처리 흐름:**
1. 전 지점 좌표 해석 (WGS84)
2. `route_url` 조립 (공식 URL 스킴)
3. 내부 경로 API 호출로 소요시간 조회 (best-effort):
   - `car` → cars.json (WGS84 그대로)
   - `bicycle`/`traffic`/`walk` → transcoord로 WCONGNAMUL 변환 후 각 엔드포인트
   - 실패(HTTP 오류, resultCode != SUCCESS, 타임아웃) 시 duration 관련 필드 null + 경고 로그
4. `arrival_time` = 호출 시각 + duration (HA 타임존 기준 ISO8601)

응답:

```yaml
route_url: https://map.kakao.com/link/by/car/집,37.5,127.0/스타벅스 판교점,37.39,127.11/회사,37.4,127.1
mode: car
duration: 2547            # 초, 실패 시 null
distance: 12481           # 미터, 실패 시 null
arrival_time: "2026-07-02T17:32:11+09:00"   # duration null이면 null
legs:                     # 출발지→경유지1, ..., →도착지
  - from: 집
    from_latitude: 37.5
    from_longitude: 127.0
    to: 스타벅스 판교점
    to_latitude: 37.39
    to_longitude: 127.11
  - ...
```

### `kakao_map.patch_map` (실험적)

필드 없음. 실행 시:
1. `hass_frontend` 패키지 디렉토리 탐색 (`importlib` 기반)
2. `frontend_es5/`, `frontend_latest/`에서 `basemaps.cartocdn.com` 포함 JS 파일 검색
3. 원본을 `.backup`으로 백업 후 타일 URL을 카카오맵 타일 URL로 치환, `.gz` 재생성
   (파일 작업은 `hass.async_add_executor_job`)
4. 패치된 파일 수를 응답으로 반환 + HA 재시작·브라우저 캐시 삭제 안내

`kakao_map.restore_map`: `.backup`으로 원복.

map_change와 달리 **원격 스크립트 다운로드 실행 금지** — 패치 로직은 컴포넌트 내 Python으로 구현.

## Code Style

HA 공식 통합 스타일 + wardrowbe의 ruff 설정(line-length 100, E/F/W/I/UP/B/SIM/RUF/PL/ANN/ASYNC/TID). 예시:

```python
async def async_search_keyword(self, query: str) -> list[dict[str, Any]]:
    """Search places by keyword and return raw documents."""
    headers = {"Authorization": f"KakaoAK {self._api_key}"}
    async with asyncio.timeout(10):
        resp = await self._session.get(
            KEYWORD_SEARCH_URL, params={"query": query}, headers=headers
        )
    if resp.status == HTTPStatus.UNAUTHORIZED:
        raise InvalidApiKey
    resp.raise_for_status()
    data = await resp.json()
    return data["documents"]
```

- 모든 I/O는 async, 이벤트 루프에서 블로킹 호출 금지
- snake_case, 타입 힌트 필수, 로그에 API 키 노출 금지
- 사용자 노출 문자열은 translations(en/ko)로

## Testing Strategy

- 실행 환경: devcontainer (Apple Container CLI로 기동), `scripts/test`
- 프레임워크: `pytest` + `pytest-homeassistant-custom-component` (HA 정렬 버전 —
  pytest/pytest-asyncio 별도 핀 금지, wardrowbe requirements_test.txt 주석 참조)
- HTTP 모킹: `aioclient_mock` (라이브러리 제공)
- 커버 대상 (우선순위 순):
  1. `api.py` — 공식 API: 정상 파싱 / 401 / 0건 / 타임아웃. 내부 API: cars 성공/ERROR, 좌표계 변환 경로
  2. 위치 해석 로직 — 엔티티(좌표 有/無) / 좌표 리스트(`[위도, 경도]`) / 형식 오류(float 아님, 2개 아님) / entity+coords 동시 지정 에러
  3. `get_directions` — URL 조립(모드별·경유지), 내부 API 실패 시 duration null 강등, traffic+경유지 에러
  4. config flow — 정상 / 잘못된 키
  5. `map_patch.py` — tmp_path 가짜 frontend 파일로 치환·백업·복원
- 실기기 검증: devcontainer의 `scripts/develop`으로 HA 기동 → 실제 API 키로 서비스 수동 호출 (사용자 수행)

## Boundaries

- **Always:**
  - 커밋 전 `scripts/test`(ruff + pytest) 통과
  - API 실패를 사용자가 이해할 수 있는 서비스 에러/경고로 변환
  - 프론트엔드 파일 수정 전 반드시 백업 생성
  - 내부 API 호출 실패 시에도 route_url은 반환 (기능 강등, 실패 아님)
- **Ask first:**
  - 신규 pip 런타임 의존성 추가
  - 카카오모빌리티 API 등 범위 밖 API 도입
  - 지도 교체 방식 변경 (패치 → 커스텀 카드 등)
  - 내부 API 엔드포인트 추가 리버스 엔지니어링 범위 확대
- **Never:**
  - API 키를 코드·로그·커밋에 포함
  - 원격 스크립트 다운로드 후 실행 (map_change 방식 금지)
  - `hass_frontend` 외 시스템 파일 수정
  - Docker 사용 (컨테이너는 Apple Container CLI)

## Success Criteria

1. Config flow에서 유효한 REST API 키로 통합 설정 완료, 잘못된 키는 에러 표시
2. `search_place`("카카오판교아지트") → 좌표·주소·`map.kakao.com/link/map/...` URL 반환
3. `get_directions`(zone 엔티티 selector + 좌표 혼합, mode=car) → 올바른 `link/by/car/...` URL,
   legs 리스트, 초 단위 duration, arrival_time 반환. 링크 클릭 시 카카오맵에 경로 표시
4. `traffic`+경유지 조합, entity/coords 동시·미지정이 명확한 에러로 거부됨
5. 내부 API 차단 상황(모킹)에서 duration=null로 강등되되 링크는 정상 반환
6. devcontainer에서 `scripts/test` 전체 통과 (ruff + pytest)
7. HACS 커스텀 저장소로 설치 가능한 구조
8. (실험적) `patch_map` 실행 후 HA 지도에 카카오 타일 표시 — Open Question 1 해소 전제

## Open Questions

1. **카카오 타일 투영 문제 (지도 교체 기능의 핵심 리스크):**
   HA 지도는 Leaflet + Web Mercator(EPSG:3857). map_change가 쓰는 네이버 타일은 Web Mercator XYZ라
   단순 URL 치환이 통하지만, **카카오 지도 타일은 자체 좌표계(WCONGNAMUL/EPSG:5181 기반)** 를 사용해
   URL 치환만으로는 타일이 어긋날 가능성이 높음. 구현 단계에서 실제 타일 URL로 검증하고,
   정렬 불가 시 보고 후 대안(네이버 타일 폴백 / 기능 제외 / 커스텀 카드) 결정.
   → 지도 교체를 마지막 태스크로 배치
2. **walkset.json 요청 계약** — 전체 파라미터 전달 시 HTTP 200이나 유효 경로에서도 NO_RESULT.
   구현 시 브라우저 devtools로 실제 요청 캡처해 확정. 미해결 시 walk 모드는 링크만 반환(duration null)
3. HA 2026.x 프론트엔드 번들에 `basemaps.cartocdn.com` 문자열 패턴이 유지되는지 — 패치 구현 시 확인
4. ~~`cars.json` 경유지(`waypoints` 파라미터) 형식~~ — **확정(2026-07-02, T7 실측)**: 경유지는
   `경도,위도,name={이름}` 형식이며 여러 개는 `|`로 연결. 단일·2개 경유지 모두 `resultCode: SUCCESS`로
   응답하고 `summary.waypoints`에 이름이 반영됨.
