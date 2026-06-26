# Architecture

Doc2Dic is a local first glossary workflow for planning documents. The MVP runs as a CLI, local API, and web surface backed by project-local SQLite storage.

## Current Implementation

| Layer | Current state |
| --- | --- |
| CLI | Typer root app with command groups registered in `src/doc2dic/cli.py`. |
| Commands | Implemented local workflows for `init`, `status`, `concept`, `variant`, `review`, `check`, `analyze`, `graph`, and `serve`. |
| Contracts | JSON Schemas under `contracts/schemas`. |
| Review domain | Review issues require human action before glossary mutations. |
| API server | FastAPI app exposes local glossary, document, review, graph, and status surfaces. It is not started by bare `doc2dic serve` yet. |
| Web UI | Local web screens consume the API and typed contract shapes. They are not started by bare `doc2dic serve` yet. |
| MCP server | `doc2dic serve --mcp` runs the doc2dic MCP server over stdio and reuses `.doc2dic/glossary.sqlite3`. |
| Installer | `doc2dic install --local --target opencode` and `doc2dic uninstall --local --target opencode` manage only the local `mcp.doc2dic` entry. |

## MVP Flow

The MVP is a locally installed `doc2dic` CLI that can be run inside a game or product planning repository. It creates project local state, analyzes Markdown or TXT files, writes candidate issues, lets a human accept or dismiss those issues, exports a graph projection, and exposes MCP context over stdio.

The project local `.doc2dic/glossary.sqlite3` database is the source of truth. Graph snapshots, Graphify compatible files, generated web types, and review findings are derived until a human accepts them.

## Trust Boundaries

| Boundary | Rule |
| --- | --- |
| LLM output | Candidate only. It must enter the review queue. |
| Embedding output | Candidate evidence only. It must not approve terms. |
| Graph projection | Derived from accepted glossary data. |
| Graphify output | Export target for viewing. Observation import is post-MVP. |
| MCP missing index | Advisory only. Agents should keep using repo tools and ask before rebuilding indexes or mutating data. |
| Stale banner | Advisory only. Pending, stale, or missing document signals do not approve changes. |
| Human review | Only accepted review actions may change authoritative concepts or variants. |

## Command Truth

| Command | Status | Architecture meaning |
| --- | --- | --- |
| `doc2dic --help` | Current | Root command group discovery. |
| `doc2dic init` | Current | Creates project-local config and SQLite storage. |
| `doc2dic status` | Current | Reports storage and optional capability state. |
| `doc2dic check samples/docs/dungeon_draft.md --write-issues` | Current | End to end document check scenario with mock providers. |
| `doc2dic review list` | Current | Review queue discovery. |
| `doc2dic graph current --json` | Current | Current derived graph projection. |
| `doc2dic graph export --format graphify` | Current | Export a Graphify compatible projection and corpus. |
| `doc2dic serve --help` | Current | Serve command discovery. |
| `doc2dic serve --mcp` | Current | MCP stdio server for the current project. |
| `doc2dic install --help` | Current | Local installer command discovery. |
| `doc2dic uninstall --help` | Current | Local uninstaller command discovery. |
| `doc2dic serve` | Planned MVP | Bare web serving is not implemented by this command yet. |
| `curl ... \| sh` | Conditional | Public hosting is not implemented. |

## Deferred Architecture

DOCX, PDF, Google Docs, Notion, and Confluence are outside the current MVP. Public release hosting is also not complete. If those surfaces are added later, they need their own tests, docs, and review queue boundaries.
