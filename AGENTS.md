# Doc2Dic Agent Ownership

Doc2Dic is a glossary driven planning document consistency checker. The source of truth is the project local `.doc2dic/glossary.sqlite3` database. Graph exports, generated web types, and review findings are derived until a human accepts them.

## Hard Rules

1. Edit only the paths assigned to your agent file under `.opencode/agents/`.
2. Don't hardcode external LLM, embedding, graph, analytics, or storage API keys.
3. Don't add auto approval logic. LLM, embedding, graph, and import findings must enter the review queue.
4. Don't call other subagents. The orchestrator owns all task routing.
5. Read contracts before changing behavior, then write `handoff/<agent-name>.md` before finishing.
6. Run the tests named in your agent file and record the command output in handoff.

## Root Wiring Gate

After Wave 0, shared root wiring is frozen unless the orchestrator gives explicit written approval for the task.

Frozen shared paths:

- `src/doc2dic/cli.py`
- `src/doc2dic/server/app.py`
- `src/doc2dic/server/routes*.py`
- `contracts/openapi.json`
- `contracts/openapi.yaml`
- `web/src/lib/api-types.ts`
- `web/src/lib/generated/**`
- `web/src/types/generated/**`

Subagents may read those paths. They must not edit them after Wave 0 unless their handoff states orchestrator approval. API shape changes, route registration changes, OpenAPI changes, and generated shared web type changes are contract freeze work, not local feature work.

## Ownership Index

| Agent | Handoff | Primary ownership |
| --- | --- | --- |
| `contract-freeze` | `handoff/contract-freeze.md` | `contracts/**`, generated shared web type contracts, root wiring review |
| `api-server` | `handoff/api-server.md` | `src/doc2dic/server/**` except frozen root wiring without approval |
| `storage` | `handoff/storage.md` | `src/doc2dic/storage/**`, `src/doc2dic/domain/**`, storage schemas |
| `glossary` | `handoff/glossary.md` | glossary services and term workflow internals |
| `analysis` | `handoff/analysis.md` | document analysis, LLM, embedding, conflict detection services |
| `review` | `handoff/review.md` | review queue services and review UI paths |
| `graph` | `handoff/graph.md` | graph projection, graphify export adapter, graph UI paths; Graphify observation import is deferred post-MVP |
| `web` | `handoff/web.md` | web shell, shared web client, common web components |
| `qa` | `handoff/qa.md` | tests, fixtures, quality scripts |
| `docs-handoff` | `handoff/docs-handoff.md` | docs, handoff summaries, agent ownership docs |

## MCP Layer Ownership Freeze

The doc2dic MCP layer is a local-first extension over the existing package and glossary database. It is not a new backend, import pipeline, or root API rewrite.

Allowed MCP-layer paths for the approved plan are:

- `src/doc2dic/mcp/**` for MCP server, registry, instructions, tool schemas, and tool allowlist code.
- `src/doc2dic/context/**` for agent-ready terminology context rendering and output budgeting.
- `src/doc2dic/sync/**` for Markdown/TXT freshness checks, reconcile helpers, stale banners, and optional local watchers.
- `src/doc2dic/installer/**` for local OpenCode install/uninstall helpers that manage only the `mcp.doc2dic` entry.
- `tests/mcp/**` for MCP protocol, allowlist, missing-index, and `doc2dic_explore` feature tests.
- `tests/context/**` for context-builder feature tests.
- `tests/sync/**` for stale-state and reconcile feature tests.
- `tests/installer/**` for local OpenCode installer/uninstaller tests.
- `tests/contracts/test_agent_ownership_docs.py` for this ownership contract.
- `docs/**` for MCP, installer, and workflow documentation.
- `handoff/**` for worker handoff files.
- `.omo/evidence/**` for task evidence files.

Frozen CLI approval for this MCP layer is limited to `doc2dic serve --mcp --path <project>` and local OpenCode install/uninstall wiring. The preferred command implementation path is `src/doc2dic/commands/serve.py`; `src/doc2dic/cli.py` may be touched only for the narrow registration needed by `serve --mcp` or install/uninstall wiring and only when the task handoff records that approval. No broad root CLI or API ownership is granted.

MCP-layer guardrails:

- No `backend/`, `backend/src/doc2dic/**`, or `backend/tests/**`.
- No `.doc2dic/doc2dic.db`; `.doc2dic/glossary.sqlite3` remains the only authoritative local database.
- No Graphify import ownership, no Graphify import API or command, and no graph-derived direct glossary mutation.
- No broad root CLI or API ownership, route registration rewrite, OpenAPI rewrite, or generated web type ownership.

Each `.opencode/agents/*.md` file must include machine readable sections named `Allowed paths`, `Forbidden paths`, `Test expectations`, and `Handoff target`.

## Handoff Format

Every agent must write `handoff/<agent-name>.md` with these headings:

1. `Task`: task id and one sentence summary.
2. `Scope`: allowed paths used and any orchestrator approval for frozen paths.
3. `Files changed`: exact file list.
4. `Commands run`: command, result, and short output summary.
5. `Evidence path`: link to `.omo/evidence/<task>.md` when the task requires evidence.
6. `Risks`: known risks or `None`.
7. `Follow-up`: proposed follow-up work or `None`.

## Contract Test

Run this before subagent work starts and after any ownership doc change:

```bash
python -m pytest tests/contracts/test_agent_ownership_docs.py -q
```
