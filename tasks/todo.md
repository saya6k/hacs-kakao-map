# TODO: HA Kakao Map

상세: tasks/plan.md 참조. 순서 = 의존성 순.

## Phase 1: Foundation
- [x] T1: 저장소 스캐폴딩 (manifest/const/hacs.json/pyproject/.gitignore, git init) — verify: manifest JSON 유효, ruff 클린
- [x] T2: devcontainer + scripts + 테스트 하네스 — verify: `container exec … scripts/test` 통과, HA 기동
- [ ] T3: config flow (API 키 검증, api.py keyword 최소 구현) — verify: test_config_flow 3케이스 + 실 키 수동
- [ ] **Checkpoint 1**: 설치·설정 가능, scripts/test 통과 → 리뷰

## Phase 2: 장소 검색
- [ ] T4: `search_place` 서비스 — verify: 정상/0건/API 오류 테스트 + "카카오판교아지트" 수동
- [ ] **Checkpoint 2**: Success Criteria #2

## Phase 3: 길찾기 링크
- [ ] T5: 위치 해석 헬퍼 (entity/coords/waypoint) — verify: test_resolve_* 통과
- [ ] T6: `get_directions` 링크+legs (ETA null) — verify: 모드별 URL/legs/에러 테스트 + 링크 수동 확인
- [ ] **Checkpoint 3**: 링크 E2E, Success Criteria #4 → 리뷰

## Phase 4: ETA (내부 API, best-effort)
- [ ] T7: car ETA (cars.json, waypoints 실측=Open Q4) — verify: 성공/강등 테스트 + 실측 근사
- [ ] T8: bicycle·traffic ETA (transcoord + bikeset/pubtrans) — verify: 파이프라인 테스트 + 실측 근사
- [ ] T9: walk ETA 조사 (walkset 계약=Open Q2, timeboxed) — verify: 연동 or 링크 전용 문서화
- [ ] **Checkpoint 4**: 전 모드 스모크, Success Criteria #3·#5

## Phase 5: 지도 교체(실험적) + 마무리
- [ ] T10: patch_map/restore_map 로직 — verify: test_map_patch (치환·백업·복원·0건)
- [ ] T11: 실 타일 정렬 검증 (Open Q1) — verify: 육안 확인, 실패 시 대안 보고→사용자 결정
- [ ] T12: README/CHANGELOG/HACS 마무리 — verify: HACS 설치 수동 확인
- [ ] **Checkpoint 5**: Success Criteria 1~7(+8) 충족, 최종 리뷰
