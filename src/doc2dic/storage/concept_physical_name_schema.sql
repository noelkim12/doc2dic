alter table concepts add column physical_name text;
create unique index if not exists idx_concepts_physical_name
  on concepts(physical_name collate nocase)
  where physical_name is not null;
