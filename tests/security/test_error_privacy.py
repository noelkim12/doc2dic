"""Security regression tests for bounded errors and privacy surfaces."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from doc2dic.domain import IssueEvidence, IssueEvidenceKind
from doc2dic.server.errors import safe_error_message
from doc2dic.services.document_context_cards import DocumentContextInput
from doc2dic.services.embedding_service import (
    EmbeddingFailure,
    EmbeddingFailureCode,
    EmbeddingService,
    embedding_provider_from_environment,
)
from doc2dic.services.llm_service import (
    AnalysisFailure,
    AnalysisFailureCode,
    LLMTermExtractionService,
    llm_provider_from_environment,
)

if TYPE_CHECKING:
    from collections.abc import Iterable


RAW_DOCUMENT_TEXT = "raw-document-start " + "전투 원문 누출 방지 " * 80
SECRET_VALUE = "sk-test-doc2dic-secret-1234567890"  # noqa: S105
ROOT = Path(__file__).resolve().parents[2]


def test_safe_error_message_redacts_raw_document_and_secret() -> None:
    message = f"provider failed with {SECRET_VALUE}: {RAW_DOCUMENT_TEXT}"

    safe_message = safe_error_message(message)
    forbidden_excerpt = "전투 원문 누출 방지 전투 원문 누출 방지 전투 원문 누출 방지"

    assert SECRET_VALUE not in safe_message
    assert forbidden_excerpt not in safe_message
    assert "[redacted-secret]" in safe_message
    assert len(safe_message) <= 240


def test_issue_evidence_contract_rejects_unbounded_quote_and_context() -> None:
    with pytest.raises(ValidationError):
        _ = IssueEvidence(
            id="evidence_too_long",
            kind=IssueEvidenceKind.QUOTE,
            source_document_id="doc_security",
            quote="q" * 601,
            context_before="before",
            context_after="after",
            confidence=1.0,
        )

    with pytest.raises(ValidationError):
        _ = IssueEvidence(
            id="evidence_context_too_long",
            kind=IssueEvidenceKind.QUOTE,
            source_document_id="doc_security",
            quote="bounded quote",
            context_before="b" * 241,
            context_after="after",
            confidence=1.0,
        )


def test_provider_failures_when_fake_api_keys_are_set_do_not_echo_secret_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DOC2DIC_LLM_PROVIDER", "openai")
    monkeypatch.setenv("DOC2DIC_LLM_API_KEY", SECRET_VALUE)
    monkeypatch.setenv("DOC2DIC_EMBEDDING_PROVIDER", "openai")
    monkeypatch.setenv("DOC2DIC_EMBEDDING_API_KEY", SECRET_VALUE)

    llm_result = LLMTermExtractionService(
        llm_provider_from_environment(),
    ).extract_terms(_sample_document())
    embedding_result = EmbeddingService(
        embedding_provider_from_environment(),
    ).embed_texts(("스태미나",))

    assert isinstance(llm_result, AnalysisFailure)
    assert llm_result.code is AnalysisFailureCode.PROVIDER_DISABLED
    assert isinstance(embedding_result, EmbeddingFailure)
    assert embedding_result.code is EmbeddingFailureCode.PROVIDER_DISABLED
    messages = (llm_result.message, embedding_result.message)
    assert SECRET_VALUE not in _joined_messages(messages)


def _joined_messages(messages: Iterable[str]) -> str:
    return "\n".join(messages)


def _sample_document() -> DocumentContextInput:
    path = ROOT / "samples" / "docs" / "combat_core.md"
    text = path.read_text(encoding="utf-8")
    return DocumentContextInput(
        document_id="combat_core",
        path="samples/docs/combat_core.md",
        title=text.splitlines()[0].removeprefix("# "),
        text=text,
    )
