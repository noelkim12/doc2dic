# Task

T14: Implemented storage-backed glossary CRUD, concept/variant/relation CLI behavior, and concept API handlers.

# Scope

Allowed paths used from the task: `src/doc2dic/services/glossary_service.py`, `src/doc2dic/commands/concept.py`, `src/doc2dic/commands/variant.py`, `src/doc2dic/commands/glossary_context.py`, `src/doc2dic/server/routes_concepts.py`, `tests/unit/services/test_glossary_service.py`, `tests/integration/cli/test_concept_variant_relation.py`, `tests/integration/server/test_concepts_api.py`, `.omo/evidence/task-14-parallel-implementation.md`, `.omo/notepads/parallel-implementation/learnings.md`, and `.omo/notepads/parallel-implementation/issues.md`.

Frozen root wiring was not edited. The task explicitly required module-local route and command implementation, so `routes_concepts.py` and command modules were updated without changing `src/doc2dic/cli.py` or `src/doc2dic/server/app.py`.

# Files changed

- `src/doc2dic/services/glossary_service.py`
- `src/doc2dic/commands/concept.py`
- `src/doc2dic/commands/variant.py`
- `src/doc2dic/commands/glossary_context.py`
- `src/doc2dic/server/routes_concepts.py`
- `tests/unit/services/test_glossary_service.py`
- `tests/integration/cli/test_concept_variant_relation.py`
- `tests/integration/server/test_app_contract.py`
- `tests/integration/server/test_concepts_api.py`
- `.omo/notepads/parallel-implementation/learnings.md`
- `.omo/notepads/parallel-implementation/issues.md`
- `.omo/evidence/task-14-parallel-implementation.md`
- `handoff/glossary.md`

# Commands run

- `/home/noel/.local/bin/python -m pytest tests/unit/services/test_glossary_service.py tests/integration/cli/test_concept_variant_relation.py tests/integration/server/test_concepts_api.py -q` - passed, `11 passed in 1.59s`.
- `/home/noel/.local/bin/python -m ruff check src/doc2dic/services/glossary_service.py src/doc2dic/commands/concept.py src/doc2dic/commands/variant.py src/doc2dic/commands/glossary_context.py src/doc2dic/server/routes_concepts.py tests/unit/services/test_glossary_service.py tests/integration/cli/test_concept_variant_relation.py tests/integration/server/test_concepts_api.py` - passed.
- `/home/noel/.local/bin/python -m basedpyright src/doc2dic/services/glossary_service.py src/doc2dic/commands/concept.py src/doc2dic/commands/variant.py src/doc2dic/commands/glossary_context.py src/doc2dic/server/routes_concepts.py tests/unit/services/test_glossary_service.py tests/integration/cli/test_concept_variant_relation.py tests/integration/server/test_concepts_api.py` - passed, `0 errors, 0 warnings, 0 notes`.
- `/home/noel/.local/bin/python -m ruff check .` - failed on non-T14 line-length errors in `tests/unit/services/test_chunking_service.py`.
- `/home/noel/.local/bin/python -m basedpyright` - failed on non-T14 errors in `src/doc2dic/services/document_parser.py` and `tests/integration/cli/test_check_exact_fuzzy.py`.
- Manual CLI smoke using `/home/noel/.local/bin/doc2dic init`, `concept add`, `variant add`, `concept relation add`, and `concept list --tag combat` - passed.

# Evidence path

`.omo/evidence/task-14-parallel-implementation.md`

# Risks

- Top-level `doc2dic relation add` was not possible without frozen root CLI edits; relation add is nested under `doc2dic concept relation add`.
- Full repository ruff and basedpyright are blocked by non-T14 files.
- `src/doc2dic/services/glossary_service.py` is oversized and should be split after acceptance.

# Follow-up

- Resolve non-T14 full-gate failures, then split glossary SQL row mapping/input models out of `glossary_service.py`.

# Atlas verification fix

T14 verification failures were fixed after root verification. The oversized service was split into `glossary_models.py`, `glossary_keys.py`, `glossary_rows.py`, and `glossary_row_mapping.py`; `glossary_service.py` now remains the stable public service/import surface. CLI glossary errors are handled in `glossary_context.py` so duplicate, not-found, and invalid-relation failures exit non-zero with concise messages and no Rich traceback. The smoke test now asserts the frozen `/api/health` path.

Additional files changed:

- `src/doc2dic/services/glossary_models.py`
- `src/doc2dic/services/glossary_keys.py`
- `src/doc2dic/services/glossary_rows.py`
- `src/doc2dic/services/glossary_row_mapping.py`
- `tests/test_smoke.py`

Additional commands run:

- `/home/noel/.local/bin/python -m pytest tests/unit/services/test_glossary_service.py tests/integration/cli/test_concept_variant_relation.py tests/integration/server/test_concepts_api.py -q` - passed, `12 passed in 1.66s`.
- `/home/noel/.local/bin/python -m pytest -q` - passed, `100 passed in 9.45s`.
- `/home/noel/.local/bin/python -m ruff check .` - passed.
- `/home/noel/.local/bin/python -m basedpyright` - passed, `0 errors, 0 warnings, 0 notes`.
- Manual invalid-relation CLI smoke - passed with `Error: relation target must differ from source` and `exit=1`.

Updated risks:

- None for T14 acceptance. Top-level `doc2dic relation add` remains intentionally unavailable because root CLI wiring is frozen; supported relation command is `doc2dic concept relation add`.

Updated follow-up:

- None.
