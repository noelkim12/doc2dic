create virtual table if not exists issue_search_fts using fts5(
  issue_id unindexed,
  surface,
  issue_type,
  status,
  concepts,
  evidence_text,
  tokenize = 'unicode61'
);
create virtual table if not exists evidence_search_fts using fts5(
  evidence_id unindexed,
  issue_id unindexed,
  source_document_id unindexed,
  chunk_id unindexed,
  quote,
  context_before,
  context_after,
  issue_surface,
  tokenize = 'unicode61'
);
insert or ignore into search_index_metadata(key, value, updated_at)
values ('issue_search_schema_version', '3', strftime('%Y-%m-%dT%H:%M:%SZ','now'));
