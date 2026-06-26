# Task

Todo 12: fixed the schema-version test regression, reran unified QA, and wrote final QA handoff evidence.

# Scope

Allowed QA/storage evidence paths used: `tests/integration/cli/test_init_status_config.py`, `.omo/evidence/**`, and `handoff/**`. No product source, frozen root wiring, OpenAPI, generated web types, provider adapter, network, Graphify import, plan checkbox, ledger, git stage, or commit work was changed.

# Files changed

- `.omo/evidence/task-12-doc2dic-codegraph-mcp-layer.md`
- `.omo/evidence/task-24-parallel-implementation.md`
- `handoff/qa.md`
- `handoff/docs-handoff.md`
- `tests/integration/cli/test_init_status_config.py`
- `/home/noel/projects/personal/doc2dic-workspace/.omo/evidence/task-12-doc2dic-codegraph-mcp-layer.md`

# Commands run

- `/home/noel/.local/bin/python -m pytest tests/integration/cli/test_init_status_config.py::test_status_when_run_in_initialized_child_directory_discovers_parent -q`: pass; `1 passed in 0.50s` after the test was updated to derive `LATEST_SCHEMA_VERSION`.
- `/home/noel/.local/bin/python -m ruff check tests/integration/cli/test_init_status_config.py`: pass; `All checks passed!`.
- `/home/noel/.local/bin/python -m basedpyright tests/integration/cli/test_init_status_config.py`: pass; `0 errors, 0 warnings, 0 notes`.
- `./scripts/test.sh --smoke`: pass; editable install completed, sqlite-vec unavailable and vector smoke skipped, Graphify available, temp project init/status/check/analyze/review/graph export completed with status reporting schema version 3, smoke mode completed.
- `./scripts/test.sh`: pass; ruff clean, basedpyright clean, provider offline tests `11 passed`, API contract tests `10 passed`, graph tests `9 passed`, Python pytest `172 passed`, web typecheck passed, web tests `150 passed`; optional web lint warned because `eslint` is not installed.
- `/home/noel/.local/bin/python -m pytest tests/mcp tests/context tests/sync tests/installer tests/contracts/test_agent_ownership_docs.py -q`: pass; `29 passed in 1.77s`.

# Evidence path

`.omo/evidence/task-12-doc2dic-codegraph-mcp-layer.md`

# Risks

- Optional web lint still warns because `eslint` is not installed; `scripts/test.sh` treats that gate as optional and exits successfully.
- `scripts/test.sh` hard-codes `.omo/evidence/task-24-parallel-implementation.md`, so the required QA runs refreshed that existing evidence file in addition to the Task 12 evidence written here.

# Follow-up

None.
