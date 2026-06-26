# Graphify Integration

Doc2Dic's MVP Graphify integration is export-only. It creates derived graph and
Markdown corpus artifacts from `.doc2dic/glossary.sqlite3`; it never imports
Graphify observations into the glossary and never mutates source glossary rows.

## Pinned Runtime Assumption

- Python package: `graphifyy`
- Executable: `graphify`
- Pinned version: `0.4.29`
- Version detection: Doc2Dic reads the executable shebang and asks that Python
  environment for `importlib.metadata.version("graphifyy")` because the observed
  executable does not support `graphify --version`.
- Observed extraction schema: `graphify.validate` requires node fields
  `id,label,file_type,source_file` and edge fields
  `source,target,relation,confidence,source_file`.

The runtime is conditional. If `graphify` is missing, version-mismatched, or the
schema probe fails, `doc2dic graph export --format graphify` still writes the
deterministic projection and records the runtime status as unavailable.

## Snapshot Layout

Exports are content-addressed under `.doc2dic/graph_snapshots/`:

```text
.doc2dic/graph_snapshots/graphify_<hash>/
  app_graph.json
  graphify_projection.json
  graphify_extraction.json
  runtime_status.json
  glossary_export/
    concepts/
      concept_*.md
```

`graphify_projection.json` follows the frozen public `GraphifyProjection`
contract: the internal `AppGraph` plus bounded Markdown documents. The separate
`graphify_extraction.json` mirrors the observed Graphify extraction fields for
future runtime processing without requiring Graphify at export time.

## Boundaries

- Exported Markdown is bounded to the public schema body limit and contains only
  glossary concept, tag, variant, and definition material.
- Provider prompts, API keys, raw provider responses, and external secrets are
  not exported.
- Graphify observation import is post-MVP and must remain behind a future review
  queue design. Do not add `graphify_import_service.py`, a Graphify import CLI,
  or `/api/graphs/graphify/import` in this MVP path.
