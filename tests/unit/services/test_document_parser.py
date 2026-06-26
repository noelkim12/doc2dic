from pathlib import Path

import pytest

from doc2dic.domain import DocumentMimeType
from doc2dic.services.document_normalization import normalize_term_text
from doc2dic.services.document_parser import (
    DocumentFormat,
    UnsupportedDocumentFormatError,
    parse_document,
)


def test_parse_document_when_markdown_has_heading_uses_heading_title(
    tmp_path: Path,
) -> None:
    path = tmp_path / "combat.md"
    _ = path.write_text("# 전투 규칙\n\n스태미나는 전투 자원이다.\n", encoding="utf-8")

    parsed = parse_document(path)

    assert parsed.title == "전투 규칙"
    assert parsed.mime_type is DocumentMimeType.MARKDOWN
    assert parsed.document_format is DocumentFormat.MARKDOWN
    assert "스태미나" in parsed.text


def test_parse_document_when_txt_has_korean_content_uses_plain_text(
    tmp_path: Path,
) -> None:
    path = tmp_path / "notes.txt"
    _ = path.write_text("입장 피로도는 매일 회복된다.\n", encoding="utf-8")

    parsed = parse_document(path)

    assert parsed.title == "notes"
    assert parsed.mime_type is DocumentMimeType.PLAIN
    assert parsed.document_format is DocumentFormat.TEXT
    assert parsed.text == "입장 피로도는 매일 회복된다.\n"


def test_parse_document_when_pdf_or_binary_path_is_unsupported(
    tmp_path: Path,
) -> None:
    pdf_path = tmp_path / "design.pdf"
    _ = pdf_path.write_bytes(b"%PDF-1.7")
    binary_path = tmp_path / "blob.bin"
    _ = binary_path.write_bytes(b"\x00\xff")

    with pytest.raises(UnsupportedDocumentFormatError, match="not supported"):
        _ = parse_document(pdf_path)
    with pytest.raises(UnsupportedDocumentFormatError, match="not supported"):
        _ = parse_document(binary_path)


def test_normalize_term_text_when_mixed_korean_english_collapses_consistently() -> None:
    assert normalize_term_text("  Stamina\tBar  ") == "stamina bar"
    assert normalize_term_text('"입장   피로도"') == "입장 피로도"
