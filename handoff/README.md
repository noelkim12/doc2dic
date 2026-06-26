# Handoff Contract

Each subagent writes exactly one handoff file at `handoff/<agent-name>.md`. The file is the integration boundary between that worker and the orchestrator.

## Required Format

Use these headings in order:

1. `Task`: task id and one sentence summary.
2. `Scope`: allowed paths used, forbidden paths avoided, and any orchestrator approval for frozen root wiring.
3. `Files changed`: exact file list, or `None`.
4. `Commands run`: command, result, and short output summary.
5. `Evidence path`: `.omo/evidence/<task>.md`, or `None` when the task has no evidence artifact.
6. `Risks`: known risks, or `None`.
7. `Follow-up`: proposed follow-up work, or `None`.

## Frozen Path Note

If a task touches `src/doc2dic/cli.py`, OpenAPI files, route registration, or generated shared web types after Wave 0, `Scope` must name the orchestrator approval. Without that approval, the handoff is invalid.

## Security And Review Rules

Don't add external API key requirements to handoff instructions. Don't create auto approval rules. Findings from LLMs, embeddings, graph imports, or document analysis remain review queue items until a human accepts them.
