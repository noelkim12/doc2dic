# Task

T26. Hardened SQLite WAL/lock behavior and preserved optional vector capability behavior under the full gate.

# Scope

Allowed storage paths used: `src/doc2dic/storage/connection.py`, `src/doc2dic/storage/vector_store.py`, and `handoff/storage.md`. No frozen root wiring, CLI, API registration, OpenAPI, generated shared web type, Graphify import, external provider, or storage schema migration file was edited.

# Files changed

- `src/doc2dic/storage/connection.py`
- `src/doc2dic/storage/vector_store.py`
- `handoff/storage.md`

# Commands run

- `/home/noel/.local/bin/python -m pytest tests/unit/storage/test_vector_store.py -q`: pass; `4 passed in 0.45s` after caching successful backend loads.
- `/home/noel/.local/bin/python -m pytest tests/security tests/integration/test_sqlite_locking.py tests/integration/test_error_payloads.py -q`: pass; `7 passed in 2.17s`.
- `scripts/test.sh`: pass; optional sqlite-vec unavailable warning remained non-fatal, full Python pytest `137 passed`.
- `/home/noel/.local/bin/python -m ruff check .`: pass; `All checks passed!`.
- `/home/noel/.local/bin/python -m basedpyright`: pass; `0 errors, 0 warnings, 0 notes`.

# Evidence path

`.omo/evidence/task-26-parallel-implementation.md`

# Risks

None.

# Follow-up

None.
