# Handoff — doc2dic `physical_name` (물리명) 기능

**날짜**: 2026-06-30 · **상태**: main 병합 + origin push 완료 · **HEAD**: `bdd9056`

## 무엇을 / 왜
glossary concept에 **코드 작명용 정식 물리명**(`physical_name`, 예: 논리명 `체력` → 물리명 `hp`)을 추가. 기획 문서는 논리명, 코드/데이터는 물리명으로 쓰되 같은 개념으로 수렴시켜 용어 일관성을 점검하기 위함.

**설계 결정**: tag(공유 분류)나 두 컬럼 분리가 아니라, 정답 1개 = `concepts.physical_name` 컬럼(nullable, 대소문자 무시 partial UNIQUE). 금지/레거시 식별자 탐지는 Plan 2로 분리.

## 변경 범위 (9 커밋, 7 태스크)

| 계층 | 파일 | 내용 |
|---|---|---|
| DB | `storage/concept_physical_name_schema.sql`, `migrations.py` | 마이그레이션 **v5** (신규 파일, schema.sql 불변). `physical_name TEXT` + `unique index ... collate nocase where not null` |
| 도메인 | `domain/concept.py` | `physical_name: str\|None`, 패턴 `^[A-Za-z_][A-Za-z0-9_]*$`, max 80 |
| 영속성 | `repositories/concepts.py`, `glossary_rows.py`, `glossary_row_mapping.py` | 두 쓰기 경로 + 두 읽기 매퍼 (15컬럼 일치) |
| 서비스 | `glossary_service.py`, `glossary_models.py`, `glossary_rows.py` | create/update 처리 + `ensure_physical_name_available` (대소문자 무시 중복 가드, update는 변경시·자기제외) |
| API | `server/routes_concepts.py`, `contracts/schemas/concept.schema.json` | camelCase `physicalName` (body·payload·contract, optional) |
| CLI | `commands/concept.py` | `--physical` (add/edit), show 출력 |
| 웹(React) | `web/src/lib/types.ts`, `ConceptForm.tsx`, `glossary/page.tsx`, `[conceptId]/page.tsx`, `glossary.test.tsx` | 폼 입력·상세 표시. **빈문자열→undefined 변환으로 422 방지** |

## 검증
- 백엔드: 258 passed (기존 실패 3건 무관), `ruff check` clean
- 프론트엔드: `tsc -b --noEmit` clean, Vitest 35/35
- 최종 전체 브랜치 리뷰(opus): **Ready to merge: Yes**, Critical 0

## 알려진 제약 / 후속 (Plan 2)
- ⚠️ **물리명 unset 불가**: 한번 설정하면 null로 못 지움(미변경과 구분 안 됨). 기존 `source_document`와 동일 컨벤션이라 의도적 보류 — 필요 시 sentinel 패턴으로 service+API+FE 보강.
- 코드 파일 스캔/점검, `TermVariantType.PHYSICAL`(금지 식별자), FE 테이블 컬럼·검색 힌트, graphify export 미포함.
- cosmetic 미적용 2건: detail 패널 `concept?.tags`→`concept.tags`, 테스트 픽스처 `yield`.

## 개발/실행 메모
- 테스트: 백엔드 `uv run pytest` (워크트리에선 `.venv/bin/pytest`), 프론트 `cd web && npm run test` / `npm run typecheck`
- 계획 문서: `docs/superpowers/plans/2026-06-29-concept-physical-name.md`
- 작업 브랜치 `feat/concept-physical-name`는 병합 후 삭제됨
