# 카카오맵 — Home Assistant 통합

> 영어 문서가 원본입니다 — [English](../en/index.md).

카카오 Local REST API와 카카오맵 웹/내부 API로 **장소 검색**, **주변 검색**, **길찾기**(카카오맵 링크 +
best-effort 소요시간)를 제공하는 Home Assistant 커스텀 통합입니다. 한국 사용자용.

> **지도 타일 교체는 지원하지 않습니다.** 프론트엔드 타일을 카카오 타일로 패치하는 방식은 (1) 카카오
> 타일이 Web Mercator(XYZ)가 아니라 URL 치환 시 빈 화면이 되고, (2) 프론트엔드의 immutable 캐시 +
> 서비스워커로 반영이 안 되어 불가능합니다.

## 기능

- **`search_place`** — 키워드 장소 검색, 상위 5건(좌표·주소·지도 링크).
- **`search_nearby`** — 중심 지점(엔티티 또는 좌표) 주변을 카테고리 또는 키워드로 거리순 검색, 각 결과에 `distance`.
- **`geocode_address`** — 주소를 WGS84 좌표로 변환, 가장 일치하는 결과의 지번·도로명 주소·우편번호·지도 링크 반환.
- **`get_directions`** — 카카오맵 경로 링크 + 구간 리스트 + best-effort 소요시간·도착 예정시간
  (자동차/대중교통/도보/자전거). 지점은 위치 보유 엔티티(person/device_tracker/zone/…) 또는 좌표.
- **Assist(AI) 툴 지원** — 동일한 기능이 AI 대화 에이전트용 LLM 툴 API로도 노출되며, 결과는 시각 카드로도 표시됩니다.
- **한국어/영어** UI 번역.

## 설치 (HACS)

1. HACS → 통합 → ⋮ → **사용자 지정 저장소** — 이 저장소 URL을 카테고리 **Integration**으로 추가.
2. **Kakao Map** 설치.
3. Home Assistant 재시작.
4. 설정 → 기기 및 서비스 → **통합 추가** → "Kakao Map" 검색.
5. 카카오 **REST API 키** 입력(카카오 개발자 → 내 애플리케이션 → 앱 키 → REST API 키). 키워드 검색 1회로 검증.

## 수동 설치

`custom_components/kakao_map/` 폴더를 HA 설정 디렉토리의 `custom_components/` 아래에 복사한 뒤 재시작합니다.

## 설정

설정 마법사는 **카카오 REST API 키** 하나를 받습니다([카카오 개발자](https://developers.kakao.com)). 단일 인스턴스만 지원합니다.

## 서비스

모든 서비스는 응답을 반환하므로 `response_variable`로 받습니다.

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

중심 지점 주변을 카테고리 **또는** 키워드로 검색(정확히 하나). 각 결과에 `distance`(m) 포함.

```yaml
# 집(zone.home) 주변 1km 카페
action: kakao_map.search_nearby
data:
  center: zone.home
  category: cafe       # 아래 목록에서 선택
  radius: 1000
response_variable: cafes
```

```yaml
# 좌표 주변 키워드 검색
action: kakao_map.search_nearby
data:
  center:
    latitude: 37.5665
    longitude: 126.978
  query: 스타벅스
  radius: 500
response_variable: nearby
```

카테고리(18종): `cafe`, `restaurant`, `convenience_store`, `supermarket`, `hospital`, `pharmacy`,
`subway_station`, `bank`, `gas_station`, `parking`, `academy`, `school`, `daycare`, `cultural_facility`,
`real_estate`, `public_institution`, `tourist_attraction`, `accommodation`. UI에는 한글 라벨(카페, 음식점 …)로
표시되고 카카오 카테고리 코드는 내부에서 처리됩니다.

18개 그룹에 없는 장소(예: 투표소/선거관리위원회)는 `query`로 검색하세요. 모든 결과에 카카오의 세부
`category_name`(예: `"사회,공공기관 > 행정기관 > 선거관리위원회"`)과 `category_group_name`이 있어 자동화에서
세분 분류로 필터할 수 있습니다.

### `kakao_map.geocode_address`

주소를 좌표로 변환합니다. 가장 일치하는 결과 1건을 반환합니다(주소를 찾지 못하면 오류 발생).

```yaml
action: kakao_map.geocode_address
data:
  query: 경기 성남시 분당구 판교역로 4
response_variable: geo
# geo: latitude / longitude / address(지번) / road_address / zone_no / map_url
```

### `kakao_map.get_directions`

```yaml
action: kakao_map.get_directions
data:
  origin: person.me                 # 엔티티 …
  destination:                      # … 또는 좌표
    latitude: 37.3945
    longitude: 127.1112
  waypoints:                        # 선택, 최대 5개
    - zone.office
  mode: car                         # car | traffic | walk | bicycle
response_variable: route
# route: route_url / mode / duration(초) / distance(m) / arrival_time / legs[]
```

## Assist(AI) 지원

동일한 4개 액션이 LLM 툴 API(`search_place`, `search_nearby`, `geocode_address`, `get_directions`)로도
등록되어 있어, AI 기반 Assist 파이프라인(예: Google Generative AI Conversation, OpenAI Conversation)이
자연어로 호출할 수 있습니다. 대화 에이전트 옵션에서 노출할 LLM API로 **Kakao Map**을 선택하면 활성화됩니다.
장소·주변 검색 결과는 카드 UI를 지원하는 Assist 화면(예: voice-satellite 대시보드)에서 시각 카드로도
표시됩니다.

## 알아두기

- **소요시간은 best-effort입니다.** `duration`/`distance`/`arrival_time`은 카카오맵 비공개 내부 API를 파싱해
  얻습니다. 변경·차단될 수 있으며, 실패 시 해당 값은 `null`로 강등되지만 **경로 링크(`route_url`)는 항상 반환**됩니다.
- **`mode: walk`는 링크 전용** — 도보 경로 API 계약 미확정으로 소요시간 등은 `null`.
- **`mode: traffic`**(대중교통)은 경유지를 지원하지 않고 응답에 `transfers`·`fare`가 추가됩니다.
- 카카오모빌리티 등 별도 가입이 필요한 API는 사용하지 않습니다.
- **지도 타일 교체 미지원** — 상단 안내 참조.
