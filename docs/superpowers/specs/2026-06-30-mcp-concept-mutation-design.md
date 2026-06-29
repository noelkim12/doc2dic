# Design — doc2dic MCP concept mutation tools

**Date**: 2026-06-30 · **Status**: approved, ready for planning

## Goal

Let an agent add / edit / delete glossary concepts through the doc2dic MCP
server **and succeed on the first call** — no trial-and-error round trips. The
driving feature is `physical_name` (물리명), which currently exists in
BE/API/CLI but is invisible and unmutable through MCP.

This reverses the prior `doc2dic-mcp-read-only` design decision (mutations were
FE+BE only). The reversal is intentional and user-approved.

## First-try success — the three mechanisms

1. **Reuse `GlossaryService`** so MCP validation is byte-for-byte identical to
   API/CLI. No second validation path, no drift.
2. **Surface every constraint up front** in the tool input schema and in the
   server instructions, so the agent constructs a valid call before sending.
3. **Return actionable guidance on every failure** (not exceptions/stack
   traces) so the agent can self-correct in one step.

## Architecture

Mutation lives in the existing `src/doc2dic/mcp/` layer and mirrors the read
tools' shape: resolve project paths → `open_database` → call `GlossaryService`
→ format result or guidance. No new database, no new validation logic —
`GlossaryService` is the single source of truth.

```
agent
  → doc2dic_create_concept(primary_term, definition, physical_name, ...)
  → schema validation (pattern / length / required)        [pre-send guard]
  → resolve project root → open_database
  → GlossaryService(conn).create_concept(CreateConceptInput(...))
      → ensure_label_available + ensure_physical_name_available
      → upsert_concept_row + insert_variant_row + replace_concept_tags
      → (embedding refresh, mirroring API)
  → markdown summary incl. new concept_id, physical_name
On DuplicateGlossaryItemError → actionable guidance, never an exception.
```

## Components

### 1. `schemas.py` — three input models

Field names snake_case (matches existing MCP schemas). Constraints mirror the
API bodies exactly.

- **`CreateConceptToolInput`**
  - `primary_term: str` (1–160)
  - `definition: str` (1–2000)
  - `term_type: ConceptTermType` (default `unknown`)
  - `tags: tuple[str, ...]` (default `()`)
  - `physical_name: str | None` (default `None`, pattern `^[A-Za-z_][A-Za-z0-9_]*$`, max 80)
  - `source_document: str | None` (default `None`)
  - `project_path: Path` (default cwd)
- **`UpdateConceptToolInput`**
  - `concept_id: str` (required)
  - all of the above fields, optional (patch semantics)
  - `status: ConceptStatus | None`
  - `project_path: Path`
- **`DeleteConceptToolInput`**
  - `concept_id: str` (required)
  - `confirm: bool` (required, must be `true`) — safety rail against accidental
    cascade hard-delete
  - `project_path: Path`

### 2. `tools.py` — three handlers

- `run_doc2dic_create_concept(...)` → `GlossaryService(conn).create_concept`.
  Catch `DuplicateGlossaryItemError` → guidance naming the conflict + remedy;
  `ValidationError` → guidance echoing the violated field + constraint; success
  → markdown summary (concept_id, primary_term, physical_name, status).
- `run_doc2dic_update_concept(...)` → `update_concept`. Catch
  `GlossaryItemNotFoundError` → not-found guidance; `DuplicateGlossaryItemError`
  → guidance (the existing self-excluding uniqueness guard is preserved).
- `run_doc2dic_delete_concept(...)` → verify `confirm is True` (else guidance),
  then `delete_concept`. Catch `GlossaryItemNotFoundError` → not-found guidance.

**Embedding refresh** mirrors the API exactly: create uses
`ProjectGlossaryEmbeddingIndexer` (so new concepts are immediately searchable);
update/delete use a plain `GlossaryService`. Implementation must verify the
indexer degrades gracefully when no embedding provider is configured (verify
point — do not let a missing provider turn a successful mutation into a failure
the agent can't interpret).

### 3. `registry.py`

Three `ToolDefinition` entries with `enabled_by_default=True`, plus aliases in
`TOOL_ALIASES`. (User chose default-on, not env opt-in.)

### 4. `server.py`

Wire the three handlers using the existing conditional `@server.tool(...)`
registration pattern in `_register_enabled_tools`.

### 5. `instructions.py` (critical for first-try)

Rewrite the `SERVER_INSTRUCTIONS`. The current
*"Do not mutate the glossary automatically"* paragraph is replaced with guidance
that:
- describes when to use the three write tools vs. the read tools;
- states the constraints inline: `physical_name` pattern + max 80,
  case-insensitive uniqueness for both primary term and physical name,
  **physical_name cannot be unset once set** (empty string is rejected);
- prescribes the workflow: run `doc2dic_explore` first to avoid duplicates,
  then `doc2dic_suggest_tags` before creating a tagged term, then create/update.

Because the tools are default-on, the instruction text is the primary
guardrail — its quality is a safety property, not just ergonomics.

### 6. `guidance.py`

Add mutation-specific guidance helpers: duplicate (term / physical_name),
not-found, invalid-input, and delete-not-confirmed.

### 7. `context/cards.py` + builder/markdown (required companion change)

Add `physical_name` to `ConceptCard` and render it in the explore output. The
agent must be able to *see* an existing physical name (e.g. `hp`) before it
tries to create/update — otherwise it hits a duplicate-physical-name failure on
the first call. This directly serves first-try success.

## Error handling — the first-try core

Schema constraints (pattern / length / required) are exposed to the agent
*before* sending, and every failure returns agent-actionable guidance:

| Failure | Guidance returned |
|---|---|
| Input constraint violated | the offending field + the constraint |
| `physical_name` duplicate | "`hp` already used by concept X — pick another or edit that concept" |
| Primary term duplicate | the conflicting term |
| Not found (update/delete) | the concept id |
| Delete without `confirm=true` | how to confirm |
| Project uninitialized / degraded | existing `missing_project_guidance` / `degraded_index_guidance` |

## Testing

`tests/mcp/`, one group per tool:
- create: success, duplicate term, duplicate physical_name (case-insensitive),
  invalid physical_name pattern
- update: success, not-found, physical_name conflict (excluding self)
- delete: success, missing `confirm`, not-found
- shared: uninitialized project, degraded database
- context: explore renders `physical_name`

Verify the full backend suite, `ruff check`, and `basedpyright` stay green.

## Out of scope for v1 (explicitly deferred)

- variant (alias / forbidden) and relation mutation
- `physical_name` unset (empty string rejected by pattern — keeps the existing
  convention; revisit with a sentinel if needed)
- audit log of mutations

## Follow-up notes

- The `doc2dic-mcp-read-only` memory is reversed by this work — update it on
  completion.
- Default-on means every installed session can write; the rewritten
  instructions are the only guardrail.
