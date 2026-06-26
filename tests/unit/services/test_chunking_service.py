from pathlib import Path
from textwrap import dedent

from doc2dic.services.document_chunking import chunk_document
from doc2dic.services.document_parser import parse_document


def test_chunk_document_when_markdown_has_headings_preserves_section_order(
    tmp_path: Path,
) -> None:
    path = tmp_path / "rules.md"
    text = dedent(
        """
        # Root

        Intro line.

        ## Combat

        스태미나는 전투 자원이다.

        ## Dungeon

        입장 피로도 설명.
        """,
    ).lstrip()
    _ = path.write_text(
        text,
        encoding="utf-8",
    )
    parsed = parse_document(path)

    chunks = chunk_document("doc_rules", parsed)

    assert tuple(chunk.section_title for chunk in chunks) == (
        "Root",
        "Combat",
        "Dungeon",
    )
    assert tuple(chunk.ordinal for chunk in chunks) == (0, 1, 2)
    assert chunks[1].raw_text == "스태미나는 전투 자원이다."
    assert chunks[1].id.startswith("chunk_")


def test_chunk_document_when_txt_has_no_heading_returns_single_fallback_chunk(
    tmp_path: Path,
) -> None:
    path = tmp_path / "notes.txt"
    _ = path.write_text("첫 줄\n둘째 줄", encoding="utf-8")
    parsed = parse_document(path)

    chunks = chunk_document("doc_notes", parsed)

    assert len(chunks) == 1
    assert chunks[0].section_title == "notes"
    assert chunks[0].raw_text == "첫 줄\n둘째 줄"
