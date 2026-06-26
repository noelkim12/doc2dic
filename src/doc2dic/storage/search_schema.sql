create table if not exists search_index_metadata (
  key text primary key,
  value text not null,
  updated_at text not null
);
create virtual table if not exists concept_search_fts using fts5(
  concept_id unindexed,
  primary_term,
  definition,
  variants,
  tags,
  tokenize = 'unicode61'
);
create virtual table if not exists document_search_fts using fts5(
  document_id unindexed,
  chunk_id unindexed,
  path,
  title,
  section_title,
  text,
  tokenize = 'unicode61'
);
insert or ignore into search_index_metadata(key, value, updated_at)
values ('search_schema_version', '2', strftime('%Y-%m-%dT%H:%M:%SZ','now'));
