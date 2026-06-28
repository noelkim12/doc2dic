# Doc2Dic

Doc2Dic is a glossary driven consistency checker for planning documents. It helps teams keep Markdown planning docs aligned with a local glossary, then routes every suggested change through human review.

The MVP is implemented as a local CLI, API, and web workflow backed by `.doc2dic/glossary.sqlite3`. Core commands run without external API keys, sqlite-vec, or Graphify. Optional capabilities are labeled below.

## What Exists Now

| Area | Status |
| --- | --- |
| Editable package install and `doc2dic` console script | Current |
| CLI commands `init`, `status`, `config`, `concept`, `variant`, `review`, `check`, `analyze`, `graph`, and `serve` | Current |
| Project-local SQLite glossary at `.doc2dic/glossary.sqlite3` | Current |
| Markdown and TXT document analysis with deterministic mock providers | Current |
| Review queue and transactional accept, dismiss, alias, forbidden-term, and relation actions | Current |
| Graph projection and Graphify-compatible export files | Current |
| Local API and web surfaces | Current through the app modules, not through `doc2dic serve` |
| MCP stdio server for OpenCode | Current through `doc2dic serve --mcp` |
| Local OpenCode MCP install and uninstall wiring | Current, local config only |
| sqlite-vec runtime search | Conditional, exact and fuzzy workflows still work without it |
| Real Graphify runtime extraction | Conditional, projection export still works without the binary |
| Public remote `curl | sh` installer | Conditional, no public hosting is claimed |

## MVP Scope

Doc2Dic's source of truth is the project local `.doc2dic/glossary.sqlite3` database. Concepts and term variants are authoritative. Review issues are the human approval boundary.

The MVP reads Markdown and TXT planning documents. DOCX, PDF, Google Docs, Notion, and Confluence integrations are post-MVP.

Graphify support is export-only. `doc2dic graph export --format graphify` writes a derived projection and Markdown corpus. Graphify observation import is post-MVP, and Graphify output must not mutate the glossary directly.

MCP support reuses the same `.doc2dic/glossary.sqlite3` database. If the MCP server reports a missing project, missing index, or degraded index, keep using normal repo search and ask before running `doc2dic init`, rebuilding indexes, or changing glossary data.

Agent context includes stale banners when known documents are pending, stale, or missing. The banner is advisory. It does not approve glossary changes and does not replace review queue decisions.

The OpenCode installer is local only. `doc2dic install --local --target opencode` writes or updates only the local `mcp.doc2dic` entry, and `doc2dic uninstall --local --target opencode` removes only that entry. Public hosted install scripts are post-MVP.

## Quickstart

From this repository, install the package in editable mode and run the same smoke flow used by the project gate:

```bash
/home/noel/.local/bin/python -m pip install -e ".[dev]"
tmpdir="$(mktemp -d)"
doc2dic --help
cd "$tmpdir"
doc2dic init
doc2dic status
DOC2DIC_LLM_PROVIDER=mock DOC2DIC_EMBEDDING_PROVIDER=mock doc2dic check /home/noel/projects/personal/doc2dic/samples/docs/dungeon_draft.md --write-issues
DOC2DIC_LLM_PROVIDER=mock DOC2DIC_EMBEDDING_PROVIDER=mock doc2dic analyze /home/noel/projects/personal/doc2dic/samples/docs/dungeon_draft.md
doc2dic review list
doc2dic graph current --json
doc2dic graph export --format graphify
```

The commands create `.doc2dic/config.toml`, `.doc2dic/glossary.sqlite3`, run checks and analysis with mock providers, and write a graph snapshot under `.doc2dic/graph_snapshots/`.

## Embedding config and auth file

`doc2dic config` is the canonical configuration surface. Run it without arguments to open a prompt for the embedding provider, model name, and API key input.

```bash
doc2dic config
doc2dic config embedding
doc2dic config embedding doctor
```

Provider and model settings are stored in the project `.doc2dic/glossary.sqlite3` settings table. API keys are stored outside the project in the user auth file. The default path is `~/.config/doc2dic/auth.json` on Linux/macOS and `%APPDATA%/.config/doc2dic/auth.json` on Windows. `XDG_CONFIG_HOME` and `DOC2DIC_AUTH_FILE` override the default path.

When the Voyage provider is selected and no model is set, Doc2Dic uses `voyage-4-large`. Runtime provider and model settings come from the project settings table, while Voyage credentials are read outside SQLite in this order:

1. `VOYAGE_API_KEY`
2. `DOC2DIC_EMBEDDING_API_KEY`
3. `DOC2DIC_AUTH_FILE`, or the default auth file value at `embedding.api_keys.voyage`

Keys entered through `doc2dic config embedding` are written only to the user auth file. `.doc2dic/glossary.sqlite3` stores provider and model settings, not raw API keys.

CLI output and `doctor` never print raw API keys; they only show whether a key is stored.

Default tests and `scripts/test.sh --smoke` stay offline and do not require a Voyage key. A live Voyage check is optional: run it only when `DOC2DIC_RUN_LIVE_VOYAGE_TESTS=1` and a supported key source are both present. The live smoke should print only non-secret metadata such as status, model, embedding count, vector dimension, and token usage.

## Command Status

| Command | Status | Notes |
| --- | --- | --- |
| `doc2dic --help` | Current | Shows the command groups. |
| `doc2dic init` | Current | Creates `.doc2dic/config.toml` and the SQLite glossary database. |
| `doc2dic status` | Current | Reports project, database, vector, and Graphify capability state. |
| `doc2dic config` | Current | Prompts for embedding provider, model, and API key storage. |
| `doc2dic config embedding` | Current | Opens the embedding configuration prompt directly. |
| `doc2dic config embedding doctor` | Current | Prints embedding config and auth-file status with secrets redacted. |
| `doc2dic concept list` | Current | Lists glossary concepts from local storage. |
| `doc2dic variant add` | Current | Adds a term variant for an existing concept. |
| `doc2dic review list` | Current | Lists review issues awaiting human action. |
| `doc2dic check samples/docs/dungeon_draft.md --write-issues` | Current | Runs deterministic document checks when mock providers are selected. |
| `doc2dic analyze samples/docs/dungeon_draft.md` | Current | Runs candidate extraction and conflict analysis. |
| `DOC2DIC_RUN_LIVE_VOYAGE_TESTS=1 ... live_voyage` | Optional | Runs live smoke only with explicit opt-in and a supported Voyage key. Default tests do not need it. |
| `doc2dic graph current --json` | Current | Prints the current derived graph projection. |
| `doc2dic graph export --format graphify` | Current | Writes Graphify-compatible projection files. Runtime Graphify execution is conditional. |
| `doc2dic serve --help` | Current | Shows the local serve surface. The implemented runtime path is MCP stdio. |
| `doc2dic serve --mcp` | Current | Starts the MCP server over stdio for the current project. Use `--path <project>` when installing into another repo. |
| `doc2dic install --help` | Current | Shows local agent installer options. Only `--local --target opencode` is implemented. |
| `doc2dic uninstall --help` | Current | Shows local agent uninstaller options. Only `--local --target opencode` is implemented. |
| `doc2dic serve` | Planned MVP | Web serving through this command is not implemented yet. |
| `curl ... \| sh` | Conditional | Public release installer path only if packaging and hosting are added later. |
| `doc2dic graph import graphify-out/graph.json` | Post-MVP | Example only. Graphify observation import is not implemented. |

## Local Verification

Run the docs consistency test after editing README or docs command tables:

```bash
/home/noel/.local/bin/python -m pytest tests/docs/test_docs_commands.py -q
```

Run the smoke gate to replay the temp-project quickstart:

```bash
scripts/test.sh --smoke
```

Run the ownership docs test after editing ownership files:

```bash
/home/noel/.local/bin/python -m pytest tests/contracts/test_agent_ownership_docs.py -q
```

## More Docs

1. `docs/architecture.md` describes the MVP architecture and trust boundaries.
2. `docs/data-model.md` describes the glossary, review, document, and graph data shapes.
3. `docs/opencode-workflow.md` describes the agent ownership workflow for this repo.
4. `docs/post-mvp.md` names deferred integrations and non-goals.
