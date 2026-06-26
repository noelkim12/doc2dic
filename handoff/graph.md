# Task

T20. Implemented Graphify-compatible export, Markdown corpus export, and conditional runtime wrapper. Follow-up fixed stale contract-stub verification for the now-implemented `/api/graphs/graphify/export` route.

# Scope

Used graph-owned service/command/API/test/docs/evidence paths: `src/doc2dic/services/graphify_adapter.py`, `src/doc2dic/services/graphify_export_service.py`, `src/doc2dic/commands/graph.py`, `src/doc2dic/server/routes_graphs.py`, graph acceptance tests, `docs/graphify-integration.md`, `.omo/evidence/task-20-parallel-implementation.md`, and `handoff/graph.md`. No frozen root CLI/app wiring, OpenAPI, generated web types, Graphify import service, import route, or glossary mutation path was edited.

# Files changed

- `src/doc2dic/services/graphify_adapter.py`
- `src/doc2dic/services/graphify_export_service.py`
- `src/doc2dic/commands/graph.py`
- `src/doc2dic/server/routes_graphs.py`
- `tests/integration/server/test_app_contract.py`
- `tests/unit/services/test_graphify_adapter.py`
- `tests/snapshots/test_graphify_projection_snapshot.py`
- `tests/integration/cli/test_graph_export.py`
- `docs/graphify-integration.md`
- `.omo/notepads/parallel-implementation/learnings.md`
- `.omo/notepads/parallel-implementation/issues.md`
- `.omo/evidence/task-20-parallel-implementation.md`
- `handoff/graph.md`

# Commands run

- `which graphify && graphify --version` - executable found at `/home/noel/.local/bin/graphify`; command exits non-zero because `--version` is unsupported.
- `/home/noel/.local/share/uv/tools/graphifyy/bin/python - <<'PY' ... PY` - verified `graphifyy 0.4.29` and no separate `graphify` distribution package.
- `/home/noel/.local/bin/python -m pytest tests/unit/services/test_graphify_adapter.py tests/snapshots/test_graphify_projection_snapshot.py tests/integration/cli/test_graph_export.py -q` - red before implementation with missing adapter/export service imports.
- `/home/noel/.local/bin/python -m pytest tests/unit/services/test_graphify_adapter.py tests/snapshots/test_graphify_projection_snapshot.py tests/integration/cli/test_graph_export.py -q` - passed, `4 passed in 0.82s`.
- `/home/noel/.local/bin/python -m ruff check .` - passed, `All checks passed!`.
- `/home/noel/.local/bin/python -m basedpyright` - passed, `0 errors, 0 warnings, 0 notes`.
- Manual CLI smoke script for `doc2dic init`, `doc2dic graph export --help`, `doc2dic graph export --format graphify`, and invalid `--format bad` - passed, `export_exit=0 nodes=3 docs=3 runtime_available=True`, `bad_exit=2 bad_has_error=True`.
- Forbidden import boundary scan - passed, no `src/doc2dic/services/graphify_import_service.py`, no production import route/service references, and only existing negative tests mention the forbidden import route/service.
- Follow-up `/home/noel/.local/bin/python -m pytest tests/integration/server/test_app_contract.py -q` before fix - failed only on stale `/api/graphs/graphify/export` 501 expectation (`assert 200 == 501`).
- Follow-up `/home/noel/.local/bin/python -m pytest tests/integration/server/test_app_contract.py -q` after fix - passed, `4 passed in 1.17s`.
- Follow-up `/home/noel/.local/bin/python -m pytest -q` - passed, `127 passed in 13.54s`.
- Follow-up `/home/noel/.local/bin/python -m ruff check .` - passed, `All checks passed!`.
- Follow-up `/home/noel/.local/bin/python -m basedpyright` - passed, `0 errors, 0 warnings, 0 notes`.
- Follow-up forbidden import boundary scan - passed, no import service file, no production import route/service references, and only existing negative tests mention the forbidden import route/service.

# Evidence path

`.omo/evidence/task-20-parallel-implementation.md`

# Risks

- `graphify_projection.json` follows the frozen `GraphifyProjection` public contract; native Graphify extraction data is emitted separately as `graphify_extraction.json` to avoid contract drift.
- Runtime execution is capability-gated because the observed `graphify` CLI lacks a stable `--version` command.
- The follow-up changed only the stale contract test expectation; it did not alter route implementation or add any Graphify import behavior.

# Follow-up

- T23 can consume the projection snapshot and should treat `runtime_status.json` as informational rather than a hard dependency.
