# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- `kakao_map.search_place`: 키워드 장소 검색, 상위 5건 리스트 반환.
- `kakao_map.search_nearby`: 중심 지점 주변을 친화적 카테고리 목록 또는 키워드로 검색(거리순 상위 5건, `distance` 포함).
- 검색 결과에 카카오 세부 분류 `category_name`·`category_group_name` 포함(문서에 있을 때) — 18개 그룹에 없는 장소(예: 투표소)도 세분 구분 가능.
- `kakao_map.get_directions`: 엔티티/좌표 입력 길찾기 — 카카오맵 링크 + 구간 리스트 + best-effort
  소요시간·도착 예정시간(car/traffic/bicycle). `traffic`은 환승·요금 부가 반환.
- Config flow: 카카오 REST API 키 입력·검증(단일 인스턴스).
- 영어/한국어 번역.

### Notes
- `mode: walk`는 링크 전용(도보 내부 API 계약 미확정으로 소요시간 `null`).
- 소요시간은 카카오맵 비공개 내부 API 기반 best-effort — 실패 시 `null` 강등, 링크는 항상 반환.

### Removed
- 실험적 지도 타일 교체(`patch_map`/`restore_map`): 카카오 타일 투영 불일치(빈 화면) + 프론트엔드
  immutable 캐시로 실현 불가함이 확인되어 폐기.
