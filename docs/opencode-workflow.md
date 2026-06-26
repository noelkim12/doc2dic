# OpenCode Workflow

This repo uses agent ownership docs to keep parallel work from crossing boundaries. Read `AGENTS.md` and the matching `.opencode/agents/<agent>.md` file before editing.

## Ownership Rules

| Rule | Meaning |
| --- | --- |
| Edit only assigned paths | Each task must stay inside the allowed paths of its agent file. |
| Keep frozen wiring frozen | Root CLI wiring, route registration, OpenAPI files, and generated shared web types are frozen after Wave 0 unless the orchestrator approves a task in writing. |
| Write a handoff | Each agent writes `handoff/<agent>.md` using `handoff/README.md`. |
| Record evidence when requested | Task evidence belongs under `.omo/evidence/`. |
| Use notepads for shared lessons | Cross task learnings and issues go under `.omo/notepads/parallel-implementation/`. |

## Docs Handoff Agent

Docs tasks may edit `README.md`, `docs/**`, `handoff/**`, `.omo/evidence/**`, and the parallel implementation notepads. Docs tasks may update `tests/docs/test_docs_commands.py` when documentation validation must match implemented command truth.

Docs tasks must not edit product source, frozen contracts, OpenAPI files, generated web types, or `.omo/plans/parallel-implementation.md`.

## MCP And Installer Ownership

MCP/context/sync/installer work stays in the existing root package. It does not create a separate backend or second database.

The MCP server instructions live in `src/doc2dic/mcp/instructions.py`. Keep that file as the single source for agent-facing server instructions. Docs may summarize the behavior, but they should not become a second instruction source.

The MCP layer reuses `.doc2dic/glossary.sqlite3`. Missing-project, missing-index, degraded-index, and stale-banner messages are advisory. Agents should keep using repo search/read tools and ask before initializing, rebuilding indexes, or changing glossary data.

Allowed paths for MCP-layer workers are `src/doc2dic/mcp/**`, `src/doc2dic/context/**`, `src/doc2dic/sync/**`, `src/doc2dic/installer/**`, `tests/mcp/**`, `tests/context/**`, `tests/sync/**`, `tests/installer/**`, `tests/contracts/test_agent_ownership_docs.py`, `docs/**`, `handoff/**`, and `.omo/evidence/**`.

Command approval is narrow: only `doc2dic serve --mcp --path <project>` and local OpenCode install/uninstall wiring may touch frozen CLI registration, and the handoff must record that approval. No broad root CLI or API ownership is granted.

Hard guardrails: No `backend/`, no `.doc2dic/doc2dic.db`, and No Graphify import ownership. Graphify remains export-only until a future post-MVP plan gives explicit ownership and review-queue rules.

## Command Documentation Rule

Any documented command must be one of these statuses:

| Status | Meaning |
| --- | --- |
| Current | The command exists and is part of the implemented MVP smoke flow or CLI surface. |
| Planned MVP | The command is an approved MVP scenario target that has not landed yet. |
| Conditional | The command depends on optional packaging, hosting, or local setup. |
| Post-MVP | The command belongs to a deferred integration. |

The docs command test checks that `Current` commands are real CLI commands. It accepts planned, conditional, and post-MVP commands only when they are labeled.

## Handoff Coverage

Every ownership agent currently has a matching handoff file:

| Agent | Handoff |
| --- | --- |
| `analysis` | `handoff/analysis.md` |
| `api-server` | `handoff/api-server.md` |
| `contract-freeze` | `handoff/contract-freeze.md` |
| `docs-handoff` | `handoff/docs-handoff.md` |
| `glossary` | `handoff/glossary.md` |
| `graph` | `handoff/graph.md` |
| `qa` | `handoff/qa.md` |
| `review` | `handoff/review.md` |
| `storage` | `handoff/storage.md` |
| `web` | `handoff/web.md` |

## Required Checks

| Command | Status | When to run |
| --- | --- | --- |
| `python -m pytest tests/docs/test_docs_commands.py -q` | Current | After editing README or docs command tables. |
| `python -m pytest tests/contracts/test_agent_ownership_docs.py -q` | Current | After editing agent ownership docs. |

## Deferred Work Boundaries

Don't describe DOCX, PDF, Google Docs, Notion, Confluence, public release hosting, bare `doc2dic serve` web serving, or Graphify observation import as complete. Keep those items in `docs/post-mvp.md` until implementation, tests, and ownership approval move them into MVP scope.
