create table if not exists concepts (
  id text primary key,
  primary_term text not null,
  definition text not null,
  term_type text not null,
  status text not null,
  tags_json text not null default '[]',
  variants_json text not null default '[]',
  scope_note text,
  non_goals_json text not null default '[]',
  examples_json text not null default '[]',
  owner text,
  created_at text not null,
  updated_at text not null
);
create table if not exists term_variants (
  id text primary key,
  concept_id text not null references concepts(id) on delete cascade,
  label text not null,
  normalized_label text not null,
  language text not null,
  variant_type text not null,
  reason text,
  status text not null,
  created_at text not null
);
create table if not exists tags (
  id text primary key,
  label text not null unique
);
create table if not exists concept_tags (
  concept_id text not null references concepts(id) on delete cascade,
  tag_id text not null references tags(id) on delete cascade,
  primary key (concept_id, tag_id)
);
create table if not exists concept_relations (
  id text primary key,
  source_concept_id text not null references concepts(id) on delete cascade,
  target_concept_id text not null references concepts(id) on delete cascade,
  relation_type text not null,
  confidence real not null,
  source_document_id text,
  status text not null
);
create table if not exists documents (
  id text primary key,
  path text not null,
  title text not null,
  content_hash text not null,
  mime_type text not null,
  chunk_ids_json text not null default '[]',
  raw_text text not null default '',
  status text not null,
  analyzed_at text not null,
  created_at text not null default (strftime('%Y-%m-%dT%H:%M:%SZ','now'))
);
create table if not exists document_chunks (
  id text primary key,
  document_id text not null references documents(id) on delete cascade,
  section_title text not null,
  ordinal integer not null,
  text_preview text not null,
  content_hash text not null,
  raw_text text not null default ''
);
create table if not exists term_occurrences (
  id text primary key,
  document_id text not null references documents(id) on delete cascade,
  chunk_id text not null references document_chunks(id) on delete cascade,
  concept_id text references concepts(id) on delete set null,
  surface text not null,
  offset_start integer not null,
  offset_end integer not null,
  confidence real not null
);
create table if not exists term_issues (
  id text primary key,
  issue_type text not null,
  status text not null,
  surface text not null,
  candidate_concept_id text references concepts(id) on delete set null,
  target_concept_id text references concepts(id) on delete set null,
  created_at text not null,
  resolved_at text,
  version integer not null default 0,
  applied_idempotency_key text
);
create table if not exists issue_evidence (
  id text primary key,
  issue_id text not null references term_issues(id) on delete cascade,
  kind text not null,
  source_document_id text not null references documents(id) on delete cascade,
  chunk_id text references document_chunks(id) on delete set null,
  quote text not null,
  context_before text not null default '',
  context_after text not null default '',
  confidence real not null
);
create table if not exists embeddings (
  id integer primary key,
  owner_type text not null,
  owner_id text not null,
  model text not null,
  dimension integer not null,
  content_hash text not null,
  created_at text not null
);
create table if not exists embedding_vectors (
  embedding_id integer primary key references embeddings(id) on delete cascade,
  vector_json text not null
);
create table if not exists graph_snapshots (
  id text primary key,
  created_at text not null,
  graph_json text not null
);
create table if not exists jobs (
  id text primary key,
  job_type text not null,
  status text not null,
  payload_json text not null default '{}',
  result_json text,
  created_at text not null,
  updated_at text not null
);
create table if not exists schema_migrations (
  version integer primary key,
  name text not null,
  checksum text not null,
  applied_at text not null
);
create table if not exists settings (
  key text primary key,
  value text not null,
  updated_at text not null
);
create index if not exists idx_term_variants_concept on term_variants(concept_id);
create index if not exists idx_document_chunks_document on document_chunks(document_id);
create index if not exists idx_term_issues_status on term_issues(status);
create index if not exists idx_issue_evidence_issue on issue_evidence(issue_id);
