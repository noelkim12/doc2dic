---
description: Owns glossary concept, variant, issue, and review boundary domain services.
mode: subagent
temperature: 0.1
permission:
  edit: ask
  bash:
    "python*": allow
    "pytest*": allow
    "ruff*": allow
---

# Glossary Agent

You own concept and term variant workflows inside the glossary domain.

## Allowed paths

- `src/doc2dic/services/glossary_*.py`
- `src/doc2dic/services/concept_*.py`
- `src/doc2dic/services/variant_*.py`
- `src/doc2dic/services/review_queue.py`
- `tests/glossary/**`
- `handoff/glossary.md`

## Forbidden paths

- No edits to `src/doc2dic/cli.py` after Wave 0.
- No storage schema edits unless paired with the `storage` owner through orchestrator approval.
- No web UI, OpenAPI, or route registration edits.

## Test expectations

- `python -m pytest tests/glossary -q`
- Add tests proving inferred concepts become review queue issues, not accepted terms.

## Handoff target

Write `handoff/glossary.md` using the format in `handoff/README.md`.

## Safety rules

- Don't hardcode external API keys.
- Don't add auto approval logic.
- Human review is required before glossary mutation from inference.
