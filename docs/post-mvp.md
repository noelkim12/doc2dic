# Post-MVP Boundaries

This page names work that should not be presented as current behavior. It can be planned later, but it needs new implementation, tests, and documentation before it leaves this page.

## Deferred Integrations

| Integration | Status | Boundary |
| --- | --- | --- |
| DOCX ingestion | Post-MVP | Markdown is the MVP input path. |
| PDF ingestion | Post-MVP | PDF centered workflows are outside MVP. |
| Google Docs | Post-MVP | No platform sync exists now. |
| Notion | Post-MVP | No platform sync exists now. |
| Confluence | Post-MVP | No platform sync exists now. |
| Bare `doc2dic serve` web serving | Planned MVP | The current implemented serve runtime is `doc2dic serve --mcp`. |
| Public release hosting | Conditional | Local OpenCode install exists, but public packaging and hosting don't. |
| Graphify observation import | Post-MVP | Import findings must become review issues and must not auto approve glossary changes. |

## Graphify Boundary

MVP graph work is projection and export only. A Graphify compatible export may be produced from Doc2Dic's accepted glossary graph, but Doc2Dic must not treat Graphify observation import as an MVP feature.

If Graphify observation import is added later, it must follow these rules:

1. Imported observations create review issues.
2. Imported observations don't directly mutate concepts, variants, or relations.
3. Tests prove that import output is not auto approved.
4. Docs label the feature as implemented only after the command and API surface exist.

## Command Table

| Command | Status | Notes |
| --- | --- | --- |
| `doc2dic graph import graphify-out/graph.json` | Post-MVP | Example name only. No current command exists. |
| `doc2dic import-docx design.docx` | Post-MVP | Example name only. No current command exists. |
| `doc2dic import-pdf design.pdf` | Post-MVP | Example name only. No current command exists. |
| `doc2dic sync notion` | Post-MVP | Example name only. No current command exists. |
| `doc2dic serve` | Planned MVP | Bare web serving is not implemented by this command yet. |

## Non-Goals For Current Docs

Don't write public release instructions as if hosting exists. Don't write platform setup guides as if OAuth apps or API keys are required. Don't claim automatic document fixes. The review queue remains the approval boundary.
