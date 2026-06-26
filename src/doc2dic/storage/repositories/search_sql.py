"""SQL builders for the v2 search repository."""


def concept_rebuild_sql() -> str:
    """Return SQL that rebuilds concept FTS rows."""
    return """
        insert into concept_search_fts(
          concept_id, primary_term, definition, variants, tags
        )
        select
          c.id,
          c.primary_term,
          c.definition,
          coalesce(group_concat(v.label || ' ' || v.normalized_label || ' '
            || v.variant_type || ' ' || v.status, ' '), ''),
          c.tags_json
        from concepts c
        left join term_variants v on v.concept_id = c.id
        group by c.id
        order by c.primary_term, c.id
        """


def document_chunk_rebuild_sql() -> str:
    """Return SQL that rebuilds document chunk FTS rows."""
    return """
        insert into document_search_fts(
          document_id, chunk_id, path, title, section_title, text
        )
        select
          d.id,
          dc.id,
          d.path,
          d.title,
          dc.section_title,
          trim(dc.text_preview || ' ' || dc.raw_text || ' '
            || coalesce(group_concat(o.surface, ' '), ''))
        from document_chunks dc
        join documents d on d.id = dc.document_id
        left join term_occurrences o on o.chunk_id = dc.id
        group by dc.id
        order by d.path, dc.ordinal, dc.id
        """


def document_without_chunk_rebuild_sql() -> str:
    """Return SQL that indexes document text when no chunks exist."""
    return """
        insert into document_search_fts(
          document_id, chunk_id, path, title, section_title, text
        )
        select d.id, null, d.path, d.title, d.title, d.raw_text
        from documents d
        where not exists (
          select 1 from document_chunks dc where dc.document_id = d.id
        )
        order by d.path, d.id
        """


def issue_rebuild_sql() -> str:
    """Return SQL that rebuilds issue FTS rows."""
    return """
        insert into issue_search_fts(
          issue_id, surface, issue_type, status, concepts, evidence_text
        )
        select
          i.id,
          i.surface,
          i.issue_type,
          i.status,
          trim(coalesce(i.candidate_concept_id, '') || ' '
            || coalesce(i.target_concept_id, '')),
          coalesce(group_concat(ie.quote || ' ' || ie.context_before || ' '
            || ie.context_after, ' '), '')
        from term_issues i
        left join issue_evidence ie on ie.issue_id = i.id
        group by i.id
        order by i.created_at, i.id
        """


def evidence_rebuild_sql() -> str:
    """Return SQL that rebuilds evidence FTS rows."""
    return """
        insert into evidence_search_fts(
          evidence_id, issue_id, source_document_id, chunk_id, quote,
          context_before, context_after, issue_surface
        )
        select
          ie.id,
          ie.issue_id,
          ie.source_document_id,
          ie.chunk_id,
          ie.quote,
          ie.context_before,
          ie.context_after,
          i.surface
        from issue_evidence ie
        join term_issues i on i.id = ie.issue_id
        order by i.created_at, ie.id
        """
