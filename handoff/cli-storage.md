# Task

T13: Implemented storage-backed `init`, `status`, and nested config commands without root CLI edits.

# Scope

Used command-local paths `src/doc2dic/commands/init.py`, `src/doc2dic/commands/status.py`, `src/doc2dic/commands/config.py`, `src/doc2dic/commands/project_state.py`, and CLI integration tests. Read frozen `src/doc2dic/cli.py` but did not edit it. No OpenAPI, route registration, generated web types, analyze/check/review/graph feature logic, external key, or network paths were changed.

# Files changed

- `src/doc2dic/commands/init.py`
- `src/doc2dic/commands/status.py`
- `src/doc2dic/commands/config.py`
- `src/doc2dic/commands/project_state.py`
- `tests/integration/cli/__init__.py`
- `tests/integration/cli/test_init_status_config.py`
- `.omo/evidence/task-13-parallel-implementation.md`
- `.omo/notepads/parallel-implementation/learnings.md`
- `.omo/notepads/parallel-implementation/issues.md`
- `.omo/start-work/ledger.jsonl`
- `handoff/cli-storage.md`

# Commands run

- `/home/noel/.local/bin/python -m pytest tests/integration/cli/test_init_status_config.py -q`: pass, `4 passed in 0.47s`.
- `/home/noel/.local/bin/python -m ruff check src/doc2dic/commands/init.py src/doc2dic/commands/status.py src/doc2dic/commands/config.py src/doc2dic/commands/project_state.py tests/integration/cli/test_init_status_config.py tests/integration/cli/__init__.py`: pass, `All checks passed!`.
- `/home/noel/.local/bin/python -m basedpyright src/doc2dic/commands/init.py src/doc2dic/commands/status.py src/doc2dic/commands/config.py src/doc2dic/commands/project_state.py tests/integration/cli/test_init_status_config.py`: pass, `0 errors, 0 warnings, 0 notes`.
- `grep -n "analyze|check|review|graph|Graphify|LLM|embedding|api_key|OPENAI|ANTHROPIC" src/doc2dic/commands/init.py src/doc2dic/commands/status.py src/doc2dic/commands/config.py src/doc2dic/commands/project_state.py tests/integration/cli/test_init_status_config.py`: pass, `0 matches`.
- Manual QA tempdir driver with `doc2dic init` then `doc2dic status`: pass, config and DB existed and status reported schema version 1.

# Evidence path

`.omo/evidence/task-13-parallel-implementation.md`

# Risks

Config get/set is nested at `doc2dic status config get/set`; root `doc2dic config` remains unavailable because adding it would require a frozen root CLI edit.

# Follow-up

If the orchestrator approves frozen root wiring, promote the nested config module to root `doc2dic config` registration.
