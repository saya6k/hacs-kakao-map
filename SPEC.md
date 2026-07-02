# Spec: HA Kakao Map (`kakao_map`)

Home Assistant 커스텀 컴포넌트. Kakao Local REST API, 카카오맵 웹 URL 스킴, 카카오맵 내부 경로 API를
이용해 장소 검색·길찾기 서비스를 제공하고, HA 기본 지도 타일을 카카오맵으로 교체(실험적)한다.

## Objective

한국 사용자용 HA 통합. 세 가지 기능:

1. **장소 검색 서비스** — 자연어 키워드로 장소를 검색해 상위 5건까지 좌표·주소·카카오맵 링크를 반환.
   중심 지점 주변을 카테고리 코드 또는 키워드로 검색하는 `search_nearby`도 제공(거리순)
2. **길찾기 서비스** — 출발/도착/경유지(선택)를 **entity selector(위치 보유 기기/엔티티) 또는 좌표**로 받아,
   이동수단(자동차/대중교통/도보/자전거)별 카카오맵 길찾기 링크 + 구간 리스트 + 소요시간·도착 예정시간을 반환
3. ~~**기본 지도 교체 서비스**~~ — **폐기(2026-07-03).** 프론트엔드 타일 URL 패치로 시도했으나
   두 가지가 실증적으로 확인되어 지원하지 않기로 결정: (a) 카카오 타일은 Web Mercator XYZ가 아니라
   URL 치환 시 빈 타일(투영 불일치, EPSG:5181), (b) HA의 immutable 해시 파일명 + 서비스워커 cache-first로
   패치가 브라우저에 반영되지 않음. 상세는 Open Q1 결론 참조.

### 사용자 결정 사항 (2026-07-02 확정)

- 카카오모빌리티 API 미사용 (별도 가입 필요). 소요시간은 카카오맵 웹 내부 API를 파싱해 획득
- "지도 이미지 링크"는 map.kakao.com 링크로 대체 (카카오는 정적 지도 이미지 REST API 없음)
- 지도 교체는 map_change 방식(프론트엔드 패치)으로 시도했으나 폐기(2026-07-03, Open Q1 결론).
  향후 앱 내 카카오 지도가 필요하면 iframe + 카카오 JS SDK 커스텀 패널이 유일한 방법(별도 옵트인 기능)
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
| 자전거 | `GET map.kakao.com/route/bikeset.json` | **WCONGNAMUL** | `sX,sY,eX,eY` (+경유지 `pX,pY,u2X,u2Y`) | `resultCode`, `directions[0].time`(초), `.length`(m) — 실측(T8) |
| 대중교통 | `GET map.kakao.com/route/pubtrans.json` | **WCONGNAMUL** | `sX,sY,eX,eY` (경유지 불가) | `in_local_status`, `in_local.routes[0].{time,distance,fare}.value`(초/m/원), `.transfers`(int) — 실측(T8) |
| 도보 | `GET map.kakao.com/route/walkset.json` | — | `sName,eName,sX,sY,eX,eY,pName,pX,pY,u2X,u2Y,ids` (누락 시 302) | **계약 미해결(T9)**: 빈 `ids`로는 항상 `NO_RESULT`. walk는 링크 전용, ETA null (Open Q2 참조) |

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
- 개발환경: devcontainer (`mcr.microsoft.com/devcontainers/python:3-3.14-bookworm`),
  Apple Container CLI로 구동

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
  services.py          # search_place / get_directions 핸들러
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
hacs.json
pyproject.toml         # ruff/mypy/pytest 설정 (wardrowbe 패턴)
SPEC.md
```

## Services

### `kakao_map.search_place`

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `query` | string | O | 검색 키워드 (예: "판교 스타벅스") |

응답 (상위 5건까지, `results` 리스트):

```yaml
results:
  - place_name: 스타벅스 판교점
    latitude: 37.39...
    longitude: 127.11...
    address: 경기 성남시 분당구 ...        # address_name
    road_address: 경기 성남시 분당구 ...   # road_address_name
    place_url: http://place.map.kakao.com/...
    map_url: https://map.kakao.com/link/map/스타벅스 판교점,37.39...,127.11...
    category_name: 음식점 > 카페 > 커피전문점 > 스타벅스   # 문서에 있을 때만
    category_group_name: 카페                              # 문서에 있을 때만
  - ...   # 검색 결과 순서대로 최대 5건
```

`category_name`/`category_group_name`은 카카오 문서에 값이 있을 때만 포함(모든 검색 공통).
18개 그룹코드에 없는 장소(예: 투표소/선거관리위원회)는 `query`로 찾고 `category_name`으로 세분 구분.

결과 0건 → `ServiceValidationError`.

### `kakao_map.search_nearby`

중심 지점 주변을 **카테고리 코드 또는 키워드**로 검색(거리순 상위 5건).

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `center` | entity_id 또는 `{latitude, longitude}` | O | 검색 중심점 (`resolve_point` 재사용) |
| `category` | string(slug) | △ | 친화적 카테고리 슬러그 (`cafe`, `restaurant`, `convenience_store` 등 18종). 내부에서 Kakao 그룹 코드(CE7/FD6/CS2…)로 변환 |
| `query` | string | △ | 검색 키워드 |
| `radius` | int(m) | X | 검색 반경, 기본 1000, 최대 20000 |

- `category`·`query`는 **정확히 하나만** 지정 (둘 다/미지정 → `ServiceValidationError` `nearby_input`)
- API: category → `search/category.json`, keyword → `search/keyword.json`(+`x`,`y`,`radius`,`sort=distance`)
- 응답: `search_place`와 동일한 `results` 리스트, 각 항목에 `distance`(m) 추가. 0건 → `ServiceValidationError`

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

### ~~`kakao_map.patch_map` / `restore_map`~~ (폐기, 2026-07-03)

프론트엔드 타일 URL 패치로 구현·검증했으나 **미지원으로 폐기**. 상세 근거는 Open Q1 결론 참조.
관련 코드(`map_patch.py`, 두 서비스, 타일 상수, 테스트)는 제거됨.

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
- 실기기 검증: devcontainer의 `scripts/develop`으로 HA 기동 → 실제 API 키로 서비스 수동 호출 (사용자 수행)

## Boundaries

- **Always:**
  - 커밋 전 `scripts/test`(ruff + pytest) 통과
  - API 실패를 사용자가 이해할 수 있는 서비스 에러/경고로 변환
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
8. ~~(실험적) 지도 타일 카카오 교체~~ — **폐기(2026-07-03).** Open Q1 결론에 따라 미지원

## Open Questions

1. ~~**카카오 타일 투영 문제**~~ — **해소·기능 폐기로 결론(2026-07-03).** 실측 결과 지도 교체 방식은
   두 층에서 막혀 지원 불가로 확정:
   - **투영 불일치**: 같은 z/x/y(서울, z14)를 실측 비교 시 cartocdn은 정상 서울 지도(96KB),
     `map.daumcdn.net/map_2d_hd/{z}/{x}/{y}`는 단색 빈 타일(311B). 카카오 타일은 EPSG:5181 자체
     좌표계라 Web Mercator XYZ URL 치환 시 **어긋나는 게 아니라 빈 화면**. 카카오는 공개 Web
     Mercator XYZ 타일 엔드포인트가 없음. (네이버/VWorld는 WM XYZ지만 카카오가 아님)
   - **캐시**: 패치된 파일을 HA가 정상 서빙해도, content-hash 파일명 + `Cache-Control: immutable
     (max-age 31일)` + 서비스워커 cache-first로 브라우저·리버스프록시가 옛 번들을 계속 사용.
     `Clear site data`/SW unregister 없이는 반영 안 됨(실증). 커뮤니티 보고와도 일치.
   - 참고: core 2024.8 PR #122430(`IndexView.canonical`/`_route`를 cached_property로)은 `/` 인덱스
     라우트 최적화일 뿐 정적파일/ETag/SW와 무관 — 캐시 문제의 원인이 아님(레드 헤링).
   → **결론**: 타일 패치 폐기. 향후 필요 시 iframe + 카카오 JS SDK 커스텀 패널(별도 옵트인)만이 유효.
2. ~~**walkset.json 요청 계약**~~ — **미해결로 확정(2026-07-02, T9 timebox)**: 전체 파라미터를
   WGS84·WCONGNAMUL 양쪽으로, 짧은 유효 경로(~1km, ~200m)로 시도해도 항상 `resultCode: NO_RESULT`
   (빈 `directions`), 파라미터 누락 시 302. `ids`(노드/링크 식별자)가 사실상 필수이며 사전 경로탐색
   호출에서 얻는 값으로 추정 — 실제 브라우저 walk 요청 캡처 없이는 재현 불가. **결론: walk 모드는
   링크 전용(duration/distance/arrival_time = null)**. 추후 캡처된 요청을 확보하면 T8과 동일 패턴으로 연동.
3. ~~HA 2026.x 프론트엔드 번들의 `basemaps.cartocdn.com` 패턴 유지 여부~~ — **확인됨(2026-07-03)**:
   2026.7 번들 `frontend_latest`/`frontend_es5`에 `basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}`
   리터럴 존재(확장자는 런타임 연결). 단 Open Q1 결론으로 지도 교체 자체를 폐기하여 무의미해짐.
4. ~~`cars.json` 경유지(`waypoints` 파라미터) 형식~~ — **확정(2026-07-02, T7 실측)**: 경유지는
   `경도,위도,name={이름}` 형식이며 여러 개는 `|`로 연결. 단일·2개 경유지 모두 `resultCode: SUCCESS`로
   응답하고 `summary.waypoints`에 이름이 반영됨.
