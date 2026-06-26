# Task

Todo 12: recorded final docs-handoff status after the schema-version regression repair and full unified QA rerun.

# Scope

Used docs-handoff owned handoff and evidence paths: `.omo/evidence/**` and `handoff/docs-handoff.md`. The only test change was the allowed CLI integration schema expectation repair. No documentation content, frozen root wiring, product source, OpenAPI, route registration, or generated shared web type files were edited.

# Files changed

- `.omo/evidence/task-12-doc2dic-codegraph-mcp-layer.md`
- `.omo/evidence/task-24-parallel-implementation.md`
- `handoff/qa.md`
- `handoff/docs-handoff.md`
- `tests/integration/cli/test_init_status_config.py`
- `/home/noel/projects/personal/doc2dic-workspace/.omo/evidence/task-12-doc2dic-codegraph-mcp-layer.md`

# Commands run

- `/home/noel/.local/bin/python -m pytest tests/integration/cli/test_init_status_config.py::test_status_when_run_in_initialized_child_directory_discovers_parent -q`: passed, `1 passed in 0.50s`.
- `/home/noel/.local/bin/python -m ruff check tests/integration/cli/test_init_status_config.py`: passed, `All checks passed!`.
- `/home/noel/.local/bin/python -m basedpyright tests/integration/cli/test_init_status_config.py`: passed, `0 errors, 0 warnings, 0 notes`.
- `./scripts/test.sh --smoke`: passed; smoke output recorded in `.omo/evidence/task-12-doc2dic-codegraph-mcp-layer.md`.
- `./scripts/test.sh`: passed; Python pytest `172 passed`, web typecheck passed, web tests `150 passed`, optional web lint warned because `eslint` is not installed.
- `/home/noel/.local/bin/python -m pytest tests/mcp tests/context tests/sync tests/installer tests/contracts/test_agent_ownership_docs.py -q`: passed, `29 passed in 1.77s`.

# Evidence path

`.omo/evidence/task-12-doc2dic-codegraph-mcp-layer.md`

# Risks

- Optional web lint still warns because `eslint` is not installed; the unified script treats it as optional.
- `scripts/test.sh` currently writes to Task 24 evidence regardless of current task id; Task 12 evidence was written separately to avoid changing the script in this FAST QA task.

# Follow-up

None.
