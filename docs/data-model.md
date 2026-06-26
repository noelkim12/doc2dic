# Data Model

Doc2Dic's data model is concept centered. The implementation stores the MVP records in project-local SQLite and keeps contract schemas aligned with the API and web surfaces.

## Source Of Truth

`.doc2dic/glossary.sqlite3` is the project local source of truth. The authoritative records are concepts and term variants. Review issues are pending decisions. Documents, chunks, occurrences, graph snapshots, and Graphify projection files are derived.

## Core Records

| Record | Role | Contract |
| --- | --- | --- |
| Concept | A canonical meaning, such as a mechanic, resource, state, action, stat, entity, rule, UI label, or lore term. | `contracts/schemas/concept.schema.json` |
| TermVariant | A label attached to a concept, such as a primary term, alias, forbidden term, deprecated term, or abbreviation. | `contracts/schemas/term_variant.schema.json` |
| TermIssue | A review queue item for an unknown term, forbidden term, conflict, alias candidate, graph relation candidate, or ambiguity. | `contracts/schemas/term_issue.schema.json` |
| IssueEvidence | A bounded quote or evidence item that supports a review issue. | `contracts/schemas/issue_evidence.schema.json` |

## Document Records

| Record | Role | Contract |
| --- | --- | --- |
| Document | A Markdown or TXT source file known to Doc2Dic. | `contracts/schemas/document.schema.json` |
| DocumentChunk | A bounded section or chunk from a document. | `contracts/schemas/document_chunk.schema.json` |
| TermOccurrence | A detected surface form in a document chunk. | `contracts/schemas/term_occurrence.schema.json` |

MVP document analysis is Markdown/TXT only. DOCX and PDF ingestion are post-MVP. Platform imports from Google Docs, Notion, and Confluence are also post-MVP.

## Graph Records

| Record | Role | Current contract |
| --- | --- | --- |
| AppGraph | Internal derived graph of concepts and relations. | `contracts/schemas/app_graph.schema.json` |
| GraphSnapshot | Timestamped graph projection derived from glossary state. | `contracts/schemas/graph_snapshot.schema.json` |
| GraphifyProjection | Export shape for Graphify compatible viewing. | `contracts/schemas/graphify_projection.schema.json` |

Graphify projection is an export boundary. Graphify observation import is post-MVP and must not be documented as current behavior.

MCP context, stale banners, and Graphify export files are derived from `.doc2dic/glossary.sqlite3` plus scanned document state. They are not a second database and they do not change concepts, variants, or relations without review actions.

## Review Boundary

Automated analysis can create issues, not accepted glossary entries. A human review action is required before a candidate becomes a concept, variant, or relation. This applies to LLM results, embedding matches, graph relation candidates, and any future import source.
