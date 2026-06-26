from doc2dic.services.document_context_cards import (
    ContextCardLimits,
    DocumentContextInput,
    GlossaryContextTerm,
    bounded_evidence_quote,
    build_context_cards,
)


def test_context_cards_truncate_document_and_bound_glossary_terms() -> None:
    document = DocumentContextInput(
        document_id="doc_combat",
        path="samples/docs/combat_core.md",
        title="전투 기본 규칙",
        text="첫 문장입니다.\n" + ("원문 누출 방지 " * 20),
    )
    glossary_terms = tuple(
        GlossaryContextTerm(
            surface=f"용어{index}",
            definition="정의 " * 20,
            concept_id=f"concept_{index}",
        )
        for index in range(5)
    )

    cards = build_context_cards(
        document,
        glossary_terms,
        ContextCardLimits(
            max_document_chars=40,
            max_quote_chars=12,
            max_glossary_terms=2,
            max_term_chars=8,
        ),
    )

    assert len(cards.document.excerpt) <= 40
    assert cards.document.excerpt.endswith("...")
    assert cards.document.excerpt != document.text.strip()
    assert cards.document.omitted_characters > 0
    assert len(cards.glossary_terms) == 2
    assert all(len(term.definition) <= 12 for term in cards.glossary_terms)


def test_bounded_evidence_quote_compacts_and_truncates_text() -> None:
    quote = bounded_evidence_quote(
        "\n  경직은 피격 직후 제한된다.  \n추가 원문",
        max_chars=16,
    )

    assert quote == "경직은 피격 직후 제한된..."
    assert "\n" not in quote
