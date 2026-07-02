# Implementation Plan: HA Kakao Map (`kakao_map`)

SPEC.md(2026-07-02 확정) 기반. 스펙의 세 기능을 수직 슬라이스로 나눠, 각 단계가 끝날 때마다
동작하는 통합(설치 가능·테스트 통과)을 유지한다.

## Overview

HA 커스텀 컴포넌트 `kakao_map`: ① 키워드 장소 검색, ② entity/좌표 입력 길찾기(링크 + best-effort
소요시간·도착 예정시간), ③ 기본 지도 타일 카카오 교체(실험적). 개발·테스트는 Apple Container CLI로
기동하는 devcontainer(ha-wardrowbe 패턴)에서 수행.

## Architecture Decisions (스펙에서 확정)

- **링크는 공식 URL 스킴, 데이터는 내부 API**: route_url은 항상 반환(공식·안정), duration/arrival_time은
  비공개 내부 API(cars/bikeset/pubtrans)로 best-effort — 실패 시 null 강등, 서비스는 성공
- **좌표 파이프라인**: 모든 지점을 WGS84로 해석 → car는 그대로, bike/traffic/walk는 공식 transcoord API로
  WCONGNAMUL 변환 후 내부 API 호출
- **의존성 없음**: HA 내장 aiohttp만 사용. 신규 pip 런타임 의존성 금지 (Ask first)
- **지도 교체는 마지막**: 카카오 타일 투영 문제(Open Q1)로 실패 가능성이 있어 다른 기능과 격리,
  자체 Python 패치(원격 스크립트 금지) + 백업/복원 서비스
- **고위험 선행 배치 예외**: 통상 고위험을 앞에 두지만, 지도 교체는 실패해도 다른 기능에 영향이 없는
  독립 기능이므로 뒤로 배치. 대신 내부 API 의존(T7)은 Phase 4 첫 태스크로 배치해 조기 검증

## Dependency Graph

```
T1 스캐폴딩 (manifest/const/pyproject/hacs.json/git)
 │
 ├─ T2 devcontainer + scripts + 테스트 하네스
 │    │
 │    └─ T3 config flow (API 키 검증)          ← KakaoLocalApi.keyword 최소 구현 필요
 │         │
 │         ├─ T4 search_place 슬라이스          (api.py keyword 완성 + 서비스)
 │         │
 │         ├─ T5 위치 해석 헬퍼 ── T6 get_directions 링크 슬라이스
 │         │                          │
 │         │                          ├─ T7 car ETA (cars.json)
 │         │                          └─ T8 transcoord + bike/traffic ETA ── T9 walk ETA (조사)
 │         │
 │         └─ T10 map_patch 로직 ── T11 실 타일 정렬 검증
 │
 └─ T12 문서/HACS 마무리 (T4·T6 이후 언제든)
```

병렬화: T4와 T5·T6은 독립(둘 다 T3 이후). T10은 T3 이후 언제든 가능. T7↔T8은 순차(api 클라이언트 공유).

## Task List

---

### Phase 1: Foundation

## Task 1: 저장소 스캐폴딩

**Description:** git 저장소 초기화와 통합의 뼈대. HA가 로드할 수 있는 최소 컴포넌트와
프로젝트 설정 파일을 만든다.

**Acceptance criteria:**
- [ ] `custom_components/kakao_map/` — manifest.json(domain=kakao_map, config_flow=true,
      iot_class=cloud_polling, version), const.py(DOMAIN·URL·모드 상수), 최소 `__init__.py`
- [ ] `hacs.json`, `pyproject.toml`(wardrowbe 패턴 ruff/mypy/pytest 설정), `.gitignore`(config/ 포함)
- [ ] git 저장소 초기화 + 최초 커밋

**Verification:**
- [ ] `python3 -c "import json; json.load(open('custom_components/kakao_map/manifest.json'))"` 통과
- [ ] `ruff check .` 클린 (호스트에서도 실행 가능)

**Dependencies:** None
**Files likely touched:** manifest.json, const.py, __init__.py, hacs.json, pyproject.toml, .gitignore
**Estimated scope:** S

## Task 2: devcontainer + 스크립트 + 테스트 하네스

**Description:** ha-chzzk/ha-wardrowbe 패턴의 devcontainer.json과 scripts/setup·develop·test,
tests 골격을 만들고 Apple Container CLI로 실제 기동을 검증한다.

**Acceptance criteria:**
- [ ] `.devcontainer/devcontainer.json`(python:3-3.13-bookworm, port 8123), `scripts/{setup,develop,test}`
      (setup: HA+테스트 의존성 설치·config/ 생성·kakao_map 심링크)
- [ ] `tests/requirements_test.txt`(pytest-homeassistant-custom-component, pytest/asyncio 별도 핀 금지),
      `tests/conftest.py`, 스모크 테스트 1건(예: manifest 로드)
- [ ] Apple Container CLI(`container run/exec`)로 컨테이너 기동 → `scripts/setup` → `scripts/test` 성공

**Verification:**
- [ ] `container exec ha-kakao-map-dev scripts/test` 통과 (ruff + pytest)
- [ ] `container exec ha-kakao-map-dev scripts/develop`로 HA 기동, http://localhost:8123 응답

**Dependencies:** Task 1
**Files likely touched:** .devcontainer/devcontainer.json, scripts/*, tests/requirements_test.txt, tests/conftest.py, tests/test_init.py
**Estimated scope:** M

## Task 3: Config Flow — API 키 입력·검증

**Description:** UI에서 카카오 REST API 키를 받아 키워드 검색 1회 호출로 유효성을 검증하고
config entry를 만든다. 이를 위해 `api.py`에 KakaoLocalApi의 keyword 검색 최소 구현을 포함한다.

**Acceptance criteria:**
- [ ] config flow: 키 입력 폼 → 검증 호출 → 성공 시 entry 생성, 401 시 `invalid_auth`,
      네트워크 오류 시 `cannot_connect` 에러 표시, 중복 설정 방지(single instance)
- [ ] `api.py`: `KakaoLocalApi.async_search_keyword()` (KakaoAK 헤더, 타임아웃, 401→InvalidApiKey)
- [ ] `translations/en.json`, `ko.json`

**Verification:**
- [ ] `tests/test_config_flow.py`: 정상/잘못된 키/연결 실패 3케이스 통과 (aioclient_mock)
- [ ] devcontainer HA UI에서 실제 키로 통합 추가 성공 (수동)

**Dependencies:** Task 2
**Files likely touched:** config_flow.py, api.py, const.py, translations/{en,ko}.json, tests/test_config_flow.py
**Estimated scope:** M

### Checkpoint 1: Foundation
- [ ] `scripts/test` 전체 통과, HA에 통합 설치·설정 가능
- [ ] 사람 리뷰 후 Phase 2 진행

---

### Phase 2: 장소 검색 슬라이스

## Task 4: `kakao_map.search_place` 서비스

**Description:** 키워드 검색 서비스 전체 경로 — services.yaml 정의, 핸들러, 응답 조립(map_url 포함),
0건 에러 처리. SPEC의 응답 스키마 그대로.

**Acceptance criteria:**
- [ ] `SupportsResponse.ONLY` 서비스 등록, `query` 필수
- [ ] 상위 1건에서 place_name/latitude/longitude/address/road_address/place_url/map_url 반환
      (map_url = `link/map/{이름},{위도},{경도}`)
- [ ] 0건 → `ServiceValidationError`(translations 메시지)

**Verification:**
- [ ] `tests/test_services.py::test_search_place*`: 정상/0건/API 오류 통과
- [ ] 수동: 실 HA에서 "카카오판교아지트" 검색 → 좌표·주소·링크 확인, 링크 클릭 시 지도 표시

**Dependencies:** Task 3
**Files likely touched:** services.py, services.yaml, __init__.py, translations/*, tests/test_services.py
**Estimated scope:** M

### Checkpoint 2: 검색 동작
- [ ] Success Criteria #2 충족 (실 키 수동 검증 포함)

---

### Phase 3: 길찾기 링크 슬라이스

## Task 5: 위치 해석 헬퍼

**Description:** entity/좌표 입력을 WGS84 좌표+이름으로 해석하는 순수 로직.
`origin_entity`/`origin_coords`(`[위도,경도]` float 2개), waypoint 항목(entity_id 또는 `"위도,경도"`) 처리.

**Acceptance criteria:**
- [ ] entity → latitude/longitude 속성 + friendly_name (속성 없으면 ServiceValidationError, 엔티티 명시)
- [ ] coords 리스트 → 좌표 (voluptuous로 float 2개 검증), 이름 "출발지"/"도착지"/"경유지N"
- [ ] entity·coords 동시/미지정, 형식 오류 → 실패 지점을 명시한 ServiceValidationError

**Verification:**
- [ ] `tests/test_services.py::test_resolve_*`: 엔티티 有/無좌표, 좌표 리스트, 오류 케이스 통과

**Dependencies:** Task 3
**Files likely touched:** services.py(또는 helpers.py), tests/test_services.py
**Estimated scope:** S

## Task 6: `kakao_map.get_directions` — 링크 + legs (ETA 제외)

**Description:** 길찾기 서비스의 골격. 지점 해석 → 공식 URL 스킴으로 route_url 조립 → legs 리스트 생성.
duration/distance/arrival_time은 이 단계에서 항상 null(구조만 존재).

**Acceptance criteria:**
- [ ] 4개 mode 토큰별 올바른 `link/by/{mode}/...` URL(출발/경유지≤5/도착 순, 이름·위도·경도)
- [ ] legs: 출발→경유지1→...→도착 쌍 리스트 (SPEC 스키마)
- [ ] `traffic`+waypoints → ServiceValidationError, waypoints>5 거부

**Verification:**
- [ ] `tests/test_services.py::test_get_directions*`: 모드별 URL/legs/검증 에러 통과
- [ ] 수동: zone 엔티티+좌표 혼합 호출 → 링크 클릭 시 카카오맵 경로 표시

**Dependencies:** Task 5
**Files likely touched:** services.py, services.yaml, translations/*, tests/test_services.py
**Estimated scope:** M

### Checkpoint 3: 길찾기 링크 E2E
- [ ] Success Criteria #3(링크 부분)·#4 충족, `scripts/test` 통과
- [ ] 사람 리뷰 후 내부 API 연동(Phase 4) 진행

---

### Phase 4: ETA (내부 경로 API — best-effort)

## Task 7: 자동차 ETA — `cars.json`

**Description:** `KakaoMapRouteApi` 신설(Referer/UA 헤더, API 키 불필요). mode=car에서
duration/distance/arrival_time 채움. 실패 시 null 강등 + 경고 로그. 경유지 waypoints 파라미터
형식 실측 검증(Open Q4).

**Acceptance criteria:**
- [ ] cars.json 호출: `origin/destination=경도,위도,name=이름`, SUCCESS 시 summary.duration/distance 파싱
- [ ] arrival_time = 호출 시각 + duration (HA 타임존 ISO8601)
- [ ] ERROR resultCode/HTTP 오류/타임아웃 → duration·distance·arrival_time null, route_url은 정상 반환
- [ ] 경유지 1·2개 실측 검증 결과를 SPEC Open Q4에 반영

**Verification:**
- [ ] `tests/test_api.py`·`test_services.py`: 성공/ERROR/타임아웃 강등 통과 (aioclient_mock)
- [ ] 수동: 실좌표 car 길찾기 → duration이 카카오맵 웹과 근사

**Dependencies:** Task 6
**Files likely touched:** api.py, services.py, const.py, tests/test_api.py, tests/test_services.py
**Estimated scope:** M

## Task 8: 자전거·대중교통 ETA — transcoord + `bikeset.json`/`pubtrans.json`

**Description:** 공식 transcoord API로 WGS84→WCONGNAMUL 변환 후 bike/traffic ETA 연동.
pubtrans는 대표 경로(ranking 1)의 time 사용, 환승·요금은 응답에 부가 필드로 포함(가능한 범위).

**Acceptance criteria:**
- [ ] `KakaoLocalApi.async_transcoord()` 구현 (WGS84→WCONGNAMUL)
- [ ] bicycle: directions[0].time/length → duration/distance
- [ ] traffic: in_local.routes[0].time → duration (+transfers/fare 부가 반환)
- [ ] 각 단계 실패 시 null 강등 유지

**Verification:**
- [ ] 모킹 테스트: 변환→호출 파이프라인, 각 모드 성공/강등 통과
- [ ] 수동: bike/traffic 실측 duration이 카카오맵 웹과 근사

**Dependencies:** Task 7
**Files likely touched:** api.py, services.py, tests/test_api.py, tests/test_services.py
**Estimated scope:** M

## Task 9: 도보 ETA — `walkset.json` 계약 확정 (조사, timeboxed)

**Description:** Open Q2 해소 시도. 브라우저 devtools로 map.kakao.com 도보 길찾기 실제 요청을
캡처해 파라미터 계약을 확정(사용자 협조 또는 chrome-devtools MCP). 1세션 timebox — 미해결이면
walk는 링크 전용으로 확정하고 SPEC·README에 문서화.

**Acceptance criteria:**
- [ ] 계약 확정 시: walk duration 연동 + 테스트 (T8과 동일 패턴)
- [ ] 미확정 시: walk=링크 전용을 SPEC Open Q2에 결론 기록, 코드에서 명시적으로 duration null

**Verification:**
- [ ] 확정 시 모킹 테스트 통과 + 실측 근사 / 미확정 시 문서·테스트(항상 null) 정합

**Dependencies:** Task 8
**Files likely touched:** api.py, services.py, SPEC.md, tests/*
**Estimated scope:** S (조사 제외 구현 소량)

### Checkpoint 4: 전 모드 ETA
- [ ] Success Criteria #3(전체)·#5 충족, 내부 API 차단 모킹 시 강등 동작
- [ ] 실 스모크: car/bicycle/traffic(가능 시 walk) 사용자가 수동 확인

---

### Phase 5: 지도 교체(실험적) + 마무리

## Task 10: `patch_map`/`restore_map` — 패치 로직

**Description:** map_patch.py — hass_frontend 탐색(importlib), cartocdn URL 치환, 백업/복원,
gzip 재생성. 파일 작업은 executor. 타일 URL은 const로 분리(실측 검증은 T11).

**Acceptance criteria:**
- [ ] patch: 대상 파일 검색→`.backup` 생성→치환→`.gz` 재생성, 패치 파일 수 반환
- [ ] restore: `.backup` 원복, 백업 없으면 명확한 에러
- [ ] 대상 파일 0건이면 오류 아닌 안내 응답 (Open Q3 대비)

**Verification:**
- [ ] `tests/test_map_patch.py`: tmp_path 가짜 frontend로 치환·백업·복원·0건 통과

**Dependencies:** Task 3 (T4~T9와 독립, 병렬 가능)
**Files likely touched:** map_patch.py, services.py, services.yaml, const.py, tests/test_map_patch.py
**Estimated scope:** M

## Task 11: 실 타일 정렬 검증 (Open Q1 해소)

**Description:** devcontainer HA에서 patch_map 실행 → 지도 카드에서 카카오 타일 정렬 확인.
투영 불일치로 어긋나면 결과를 정리해 사용자에게 대안(네이버 폴백/기능 제외/커스텀 카드) 결정 요청.

**Acceptance criteria:**
- [ ] 정렬 성공: Success Criteria #8 충족, 스크린샷/확인 기록
- [ ] 정렬 실패: 증상·원인 정리 + 대안 제시 → 사용자 결정 (Ask first 경계)

**Verification:**
- [ ] devcontainer HA 지도 카드 육안 확인 (restore_map으로 원복 가능 확인 포함)

**Dependencies:** Task 10
**Files likely touched:** const.py(타일 URL), SPEC.md(결론 기록)
**Estimated scope:** S (조사 중심)

## Task 12: 문서·HACS 마무리

**Description:** README(ko 중심, 설치·서비스 사용 예시·내부 API 리스크 고지), CHANGELOG,
HACS 설치 검증.

**Acceptance criteria:**
- [ ] README: HACS/수동 설치, 서비스 3종 예시(YAML), ETA best-effort·실험적 기능 고지
- [ ] hacs.json 유효, 저장소 구조로 HACS 커스텀 저장소 추가 가능

**Verification:**
- [ ] HACS에 커스텀 저장소로 추가→설치 성공 (수동)

**Dependencies:** Task 6 이후 (내용상 T9·T11 결과 반영이 이상적)
**Files likely touched:** README.md, CHANGELOG.md, hacs.json
**Estimated scope:** S

### Checkpoint 5: Complete
- [ ] SPEC Success Criteria 1~7 전부(+8은 T11 결과에 따라) 충족
- [ ] `scripts/test` 클린, 최종 사람 리뷰

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| 내부 경로 API 변경·차단 (carset.json 전례) | High | best-effort 설계: 링크는 항상 반환, null 강등 + 경고. 클라이언트를 api.py 한 곳에 격리 |
| 카카오 타일 투영 불일치로 지도 교체 실패 | Med | 독립 기능으로 격리, restore 제공, T11에서 조기 판정 후 사용자 결정 |
| walkset.json 계약 미확정 | Low | T9 timebox, 미해결 시 링크 전용으로 명시적 강등 |
| HA 프론트엔드 번들에서 cartocdn 패턴 소멸 | Med | 패치 대상 0건을 정상 응답으로 처리, 버전별 패턴 재조사 |
| Apple Container CLI와 devcontainer 도구 비호환 | Low | devcontainer.json은 VS Code용으로 유지하되 CLI 기동 명령을 README/스크립트로 별도 제공 |
| pytest 의존성 충돌 (pytest-asyncio 핀) | Low | wardrowbe 교훈 적용: pytest-homeassistant-custom-component에 버전 위임 |

## Open Questions (SPEC과 동기)

- Open Q1: 카카오 타일 투영 — T11에서 판정
- Open Q2: walkset 계약 — T9에서 판정 (브라우저 devtools 캡처에 사용자 협조 필요할 수 있음)
- Open Q3: cartocdn 패턴 유지 여부 — T10/T11에서 확인
- Open Q4: cars.json waypoints 형식 — T7에서 실측
