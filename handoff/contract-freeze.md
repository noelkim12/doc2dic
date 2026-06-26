# Task

T2: Freeze public contracts, schemas, OpenAPI, and generated/shared web types.

# Scope

Used `contracts/**`, `tests/contracts/**`, `web/src/lib/types.ts`, `handoff/contract-freeze.md`, and required OMO evidence/notepad/ledger paths. Avoided T1 frozen root wiring, including `src/doc2dic/cli.py`, `src/doc2dic/server/app.py`, and route registration files. `web/src/lib/types.ts` was explicitly requested by T2 even though the contract-freeze agent file lists generated shared web type paths.

# Files changed

- `contracts/openapi.yaml`
- `contracts/schemas/concept.schema.json`
- `contracts/schemas/term_variant.schema.json`
- `contracts/schemas/document.schema.json`
- `contracts/schemas/document_chunk.schema.json`
- `contracts/schemas/term_occurrence.schema.json`
- `contracts/schemas/issue_evidence.schema.json`
- `contracts/schemas/term_issue.schema.json`
- `contracts/schemas/app_graph.schema.json`
- `contracts/schemas/graph_snapshot.schema.json`
- `contracts/schemas/graphify_projection.schema.json`
- `contracts/schemas/llm_term_candidates.schema.json`
- `contracts/schemas/llm_conflict_classification.schema.json`
- `web/src/lib/types.ts`
- `tests/contracts/test_public_contracts.py`
- `.omo/evidence/task-2-parallel-implementation.md`
- `.omo/notepads/parallel-implementation/learnings.md`
- `.omo/start-work/ledger.jsonl`
- `handoff/contract-freeze.md`

# Commands run

- `zsh -lc 'python -m pytest tests/contracts -q'`: passed, `21 passed in 0.06s`.
- `python -m basedpyright tests/contracts/test_public_contracts.py`: passed, `0 errors, 0 warnings, 0 notes`.
- Grep scan for `graphify_import_service|GraphifyImportService` in Python files: no matches.
- Glob cleanup check for `tests/contracts/__pycache__/**` and `.pytest_cache/**`: no files found.

# Evidence path

`.omo/evidence/task-2-parallel-implementation.md`

# Risks

`web/src/lib/types.ts` was created because T2 explicitly required it; future workers should treat it as the shared contract mirror unless the orchestrator migrates to generated paths.

# Follow-up

None.
