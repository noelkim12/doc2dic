# Task

T26. Hardened API error payloads for privacy, bounded messages, and friendly SQLite lock failures.

# Scope

Allowed API-server paths used: `src/doc2dic/server/errors.py`, `src/doc2dic/server/routes_graphs.py`, `src/doc2dic/server/routes_issues.py`, and `handoff/api-server.md`. Frozen route registration in `src/doc2dic/server/app.py`, OpenAPI contracts, generated shared web types, and `src/doc2dic/cli.py` were not edited. No orchestrator approval for frozen root wiring was needed.

# Files changed

- `src/doc2dic/server/errors.py`
- `src/doc2dic/server/routes_graphs.py`
- `src/doc2dic/server/routes_issues.py`
- `handoff/api-server.md`

# Commands run

- `/home/noel/.local/bin/python -m pytest tests/security tests/integration/test_sqlite_locking.py tests/integration/test_error_payloads.py -q`: pass; `7 passed in 2.17s`.
- `scripts/test.sh`: pass; API contract tests `9 passed`, full Python pytest `137 passed`.
- `/home/noel/.local/bin/python -m ruff check .`: pass; `All checks passed!`.
- `/home/noel/.local/bin/python -m basedpyright`: pass; `0 errors, 0 warnings, 0 notes`.

# Evidence path

`.omo/evidence/task-26-parallel-implementation.md`

# Risks

None.

# Follow-up

None.
