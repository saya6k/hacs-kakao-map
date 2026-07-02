# TODO: HA Kakao Map

상세: tasks/plan.md 참조. 순서 = 의존성 순.

## Phase 1: Foundation
- [x] T1: 저장소 스캐폴딩 (manifest/const/hacs.json/pyproject/.gitignore, git init) — verify: manifest JSON 유효, ruff 클린
- [x] T2: devcontainer + scripts + 테스트 하네스 — verify: `container exec … scripts/test` 통과, HA 기동
- [x] T3: config flow (API 키 검증, api.py keyword 최소 구현) — verify: test_config_flow 3케이스 + 실 키 수동
- [x] **Checkpoint 1**: 설치·설정 가능, scripts/test 통과 → 리뷰 (2026-07-02 실 키 등록·오류 표시 수동 확인)

## Phase 2: 장소 검색
- [x] T4: `search_place` 서비스 — verify: 정상/0건/API 오류 테스트 + "카카오판교아지트" 수동
- [x] **Checkpoint 2**: Success Criteria #2 (2026-07-02 실 HA에서 카카오판교아지트 검색 응답 확인)

## Phase 3: 길찾기 링크
- [x] T5: 위치 해석 헬퍼 (지점=entity_id 또는 location dict) — verify: test_resolve_* 통과 (순수 로직이라 T3보다 먼저 구현)
      ※ 사용자 확정: 지점당 단일 필드(`origin`/`destination`), 값은 entity_id 또는 `{latitude, longitude}` 매핑.
        entity/좌표 필드를 분리하지 않음. waypoints도 entity 또는 좌표 혼용. SPEC 반영 완료.
- [x] T6: `get_directions` 링크+legs (ETA null) — verify: 모드별 URL/legs/에러 테스트 통과 (2026-07-02). 링크 수동 확인은 사용자 몫
- [x] **Checkpoint 3**: 링크 E2E, Success Criteria #4 → 리뷰 (2026-07-02 사용자 승인, scripts/test 통과)

## Phase 4: ETA (내부 API, best-effort)
- [x] T7: car ETA (cars.json, waypoints 실측=Open Q4) — verify: 성공/강등 테스트 통과 (2026-07-02). 실측: 서울시청→강남 duration≈1195s, 경유지 `경도,위도,name=` `|` 연결 확정 (Open Q4 해소)
- [x] T8: bicycle·traffic ETA (transcoord + bikeset/pubtrans) — verify: 파이프라인 테스트 통과 (2026-07-02). 실측: bike≈3531s/14.5km, transit≈2949s/49분·1650원. pubtrans는 `{value}` 중첩 필드(SPEC 표 정정). bike+경유지는 ETA null(bikeset 경유지 미모델링)
- [ ] T9: walk ETA 조사 (walkset 계약=Open Q2, timeboxed) — verify: 연동 or 링크 전용 문서화
- [ ] **Checkpoint 4**: 전 모드 스모크, Success Criteria #3·#5

## Phase 5: 지도 교체(실험적) + 마무리
- [ ] T10: patch_map/restore_map 로직 — verify: test_map_patch (치환·백업·복원·0건)
- [ ] T11: 실 타일 정렬 검증 (Open Q1) — verify: 육안 확인, 실패 시 대안 보고→사용자 결정
- [ ] T12: README/CHANGELOG/HACS 마무리 — verify: HACS 설치 수동 확인
- [ ] **Checkpoint 5**: Success Criteria 1~7(+8) 충족, 최종 리뷰
