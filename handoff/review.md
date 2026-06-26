# Task

T18: Implemented transactional review service actions, review CLI commands, and issue API handlers.

# Scope

- Used review task paths: `src/doc2dic/services/review_*.py`, `src/doc2dic/commands/review.py`, `src/doc2dic/server/routes_issues.py`, review-focused tests, evidence, notepads, and this handoff.
- Touched `src/doc2dic/services/glossary_service.py` to make existing glossary mutations respect an active outer SQLite transaction.
- Touched `src/doc2dic/storage/repositories/issues.py` to add issue listing needed by the review service while preserving existing repository commit behavior.
- No edits to frozen root wiring (`src/doc2dic/cli.py`, `src/doc2dic/server/app.py`), OpenAPI, generated web types, storage schema, provider logic, graph projection, web UI, or document parsing.

# Files changed

- `src/doc2dic/services/glossary_service.py`
- `src/doc2dic/services/review_effects.py`
- `src/doc2dic/services/review_models.py`
- `src/doc2dic/services/review_service.py`
- `src/doc2dic/storage/repositories/issues.py`
- `src/doc2dic/commands/review.py`
- `src/doc2dic/server/routes_issues.py`
- `tests/unit/services/test_review_service.py`
- `tests/integration/cli/test_review_commands.py`
- `tests/integration/server/test_issues_api.py`
- `tests/integration/server/test_app_contract.py`
- `.omo/evidence/task-18-parallel-implementation.md`
- `.omo/notepads/parallel-implementation/learnings.md`
- `.omo/notepads/parallel-implementation/issues.md`
- `handoff/review.md`

# Commands run

- `/home/noel/.local/bin/python -m pytest tests/unit/services/test_review_service.py tests/integration/cli/test_review_commands.py tests/integration/server/test_issues_api.py -q` - passed, `11 passed in 2.03s`.
- `/home/noel/.local/bin/python -m pytest -q` - passed, `122 passed in 13.18s`.
- `/home/noel/.local/bin/python -m ruff check .` - passed, all checks passed.
- `/home/noel/.local/bin/python -m basedpyright` - passed, `0 errors, 0 warnings, 0 notes`.
- `/home/noel/.local/bin/python -m pytest tests/contracts/test_agent_ownership_docs.py -q` - passed, `6 passed in 0.01s`.
- `doc2dic review --help` - passed, showed list/show/dismiss/resolve commands.
- `doc2dic init` in `/tmp/opencode/doc2dic-t18-manual` - passed, initialized config and database.
- `doc2dic review list` - passed, printed `issue_manual open ManualTerm`.
- `doc2dic review show issue_manual` - passed, printed status open and version 0.
- `doc2dic review dismiss issue_manual --expected-version 9 --idempotency-key manual-bad --reason stale` - passed bad-input QA, returned concise stale-version error.
- `doc2dic review resolve-as-new-concept issue_manual --expected-version 0 --idempotency-key manual-new --term ManualTerm --definition "Manual QA concept"` - passed, applied action.
- Replayed the same resolve command - passed, returned `already_applied` without duplicate rows.
- ASGI API smoke against `/api/issues/issue_manual` and `/api/issues/issue_manual/dismiss` - passed, returned resolved issue payload then `409 issue_closed`.

# Evidence path

`.omo/evidence/task-18-parallel-implementation.md`

# Risks

- Generic `/api/issues/{issue_id}/accept` carries relation actions because adding `/resolve-as-relation` would require frozen OpenAPI contract work.
- `tests/integration/server/test_app_contract.py` now excludes implemented issue routes and the pre-existing implemented `/api/graphs/current` route from the 501 stub list.

# Follow-up

- Decide in a contract-freeze task whether relation review should receive an explicit OpenAPI route.
