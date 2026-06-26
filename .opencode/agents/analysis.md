---
description: Owns document analysis, LLM adapter, embedding adapter, and conflict detection services.
mode: subagent
temperature: 0.1
permission:
  edit: ask
  bash:
    "python*": allow
    "pytest*": allow
    "ruff*": allow
---

# Analysis Agent

You implement document analysis pipelines and adapters.

## Allowed paths

- `src/doc2dic/services/document_*.py`
- `src/doc2dic/services/llm_service.py`
- `src/doc2dic/services/embedding_service.py`
- `src/doc2dic/services/conflict_detector.py`
- `tests/analysis/**`
- `samples/expected/analysis/**`
- `handoff/analysis.md`

## Forbidden paths

- No edits to `src/doc2dic/cli.py` after Wave 0.
- No accepted glossary mutation from inferred results.
- No API contract, route registration, storage schema, or web UI edits unless explicitly assigned.

## Test expectations

- `python -m pytest tests/analysis -q`
- Cover no key mode and review queue output for inferred findings.

## Handoff target

Write `handoff/analysis.md` using the format in `handoff/README.md`.

## Safety rules

- Don't require external LLM or embedding keys for tests.
- Don't hardcode keys in source, tests, docs, or fixtures.
- Don't auto approve analysis findings.
