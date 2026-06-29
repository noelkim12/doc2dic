# Handoff — doc2dic MCP concept mutation tools

**날짜**: 2026-06-30 · **상태**: main 병합 대기 · **HEAD**: `b846194`

## 무엇을 / 왜
MCP 서버에 **glossary concept 직접 쓰기 도구 3종**(`doc2dic_create_concept`, `doc2dic_update_concept`, `doc2dic_delete_concept`)을 추가. 기존 MCP는 읽기 전용이었으나, AI 어시스턴트가 용어 추가·수정·삭제를 실행할 수 있도록 설계를 의도적으로 전환. 함께 `physical_name`(물리명)을 `doc2dic_explore` 응답 컨텍스트에 노출.

**설계 전환**: 이전 "doc2dic MCP is read-only" 결정을 사용자 승인 하에 철회. 세 도구는 기본 활성(default-on)으로 등록.

**설계 결정 — embedding indexer 미포함**: 뮤테이션 경로에서 `SearchIndexRepository`(Voyage embedding)를 사용하지 않음. 외부 임베딩 제공자 의존 없이 기본 CRUD를 보장하기 위함. 신규 개념은 다음 `doc2dic index` 실행 이후부터 유사 검색에 노출됨.

## 변경 범위 (6 태스크)

| 계층 | 파일 | 내용 |
|---|---|---|
| context | `src/doc2dic/context/cards.py` | `physical_name` 필드를 explore 컨텍스트 카드에 포함 |
| MCP 스키마 | `src/doc2dic/mcp/schemas.py` | Pydantic 입력 스키마 3종: `CreateConceptInput`, `UpdateConceptInput`, `DeleteConceptInput` |
| MCP 가이던스 | `src/doc2dic/mcp/guidance.py` | 뮤테이션 도구용 가이던스 헬퍼 4종 추가 |
| MCP 도구 핸들러 | `src/doc2dic/mcp/tools.py` | `run_doc2dic_create_concept`, `run_doc2dic_update_concept`, `run_doc2dic_delete_concept` (GlossaryService 직접 호출) |
| MCP 레지스트리 | `src/doc2dic/mcp/registry.py` | 세 도구 `enabled_by_default=True`로 등록 |
| MCP 서버 | `src/doc2dic/mcp/server.py`, `src/doc2dic/mcp/instructions.py` | 세 도구 라우팅 추가, 서버 instructions 재작성 (기존 "Do not mutate the glossary automatically" 라인 제거) |
| 테스트 | `tests/mcp/test_mutation_schemas.py`, `tests/mcp/test_mutation_guidance.py`, `tests/mcp/test_mutation_tools.py`, `tests/mcp/test_mutation_server.py` (추가); `tests/mcp/test_doc2dic_explore.py`, `tests/context/test_explore_context_builder.py` (수정) | 뮤테이션 도구 단위 검증 추가 |

## 검증
- 백엔드: 281 passed, 1 skipped (기존 실패 2건 무관: `test_serve_help_exposes_mcp_and_path_options` ANSI 렌더 아티팩트, `test_contract_routes_return_501_schema_when_called` Voyage 503 미스매치)
- `ruff check src tests`: 기존 I001 11건(테스트 파일 import 정렬) — feature 파일 미해당
- `basedpyright src/doc2dic/mcp src/doc2dic/context`: **0 errors, 0 warnings, 0 notes**

## 알려진 제약 / v1 범위

- **variant·relation 뮤테이션 미포함**: 이번 v1은 concept CRUD만; 별칭(alias), 금지어(forbidden), relation 추가·삭제는 별도 계획.
- **`physical_name` unset 불가**: 빈 문자열은 패턴 `^[A-Za-z_][A-Za-z0-9_]*$` 검증 실패로 거부됨. 한번 설정한 물리명을 null로 되돌리려면 sentinel 패턴 추가 필요 (기존 `physical_name` 핸들오프와 동일 보류).
- **audit log 없음**: 뮤테이션 이력 기록 미구현.
- **embedding 재인덱싱 자동화 없음**: 신규·수정 개념은 다음 `doc2dic index` 실행 후 유사 검색 가능.

## 개발/실행 메모
- 테스트: `PYTHONPATH=. .venv/bin/pytest tests/mcp tests/context` (워크트리 기준)
- 전체 수트: `PYTHONPATH=. .venv/bin/pytest -q`
- MCP 도구 목록 확인: `DOC2DIC_MCP_TOOLS=status doc2dic serve --mcp --path .`
- 계획 문서: `.superpowers/sdd/` 아래 task-1 ~ task-6 brief/report
