from dataclasses import dataclass
from pathlib import Path

import pytest

from doc2dic.services.document_context_cards import (
    AnalysisContextCards,
    DocumentContextInput,
)
from doc2dic.services.llm_service import (
    AnalysisFailure,
    AnalysisFailureCode,
    DeterministicMockLLMProvider,
    DisabledLLMProvider,
    LLMEvidence,
    LLMProviderError,
    LLMServiceConfig,
    LLMTermCandidate,
    LLMTermCandidatesOutput,
    LLMTermExtractionService,
    TermExtractionSuccess,
    TermType,
    llm_provider_from_environment,
)

ROOT = Path(__file__).resolve().parents[3]


@dataclass(slots=True)
class SequencedLLMProvider:
    responses: list[str]
    provider_name: str = "sequenced"
    calls: int = 0

    def extract_term_candidates(self, context: AnalysisContextCards) -> str:
        _ = context
        self.calls += 1
        return self.responses.pop(0)


class BrokenLLMProvider:
    provider_name: str = "broken"

    def extract_term_candidates(self, context: AnalysisContextCards) -> str:
        _ = context
        message = "provider transport failed"
        raise LLMProviderError(message)


def test_mock_llm_extracts_sample_combat_terms_when_document_matches_fixture() -> None:
    document = _sample_document("combat_core.md")
    service = LLMTermExtractionService(DeterministicMockLLMProvider())

    result = service.extract_terms(document)

    assert isinstance(result, TermExtractionSuccess)
    assert result.provider == "deterministic_mock"
    assert tuple(candidate.surface for candidate in result.candidates) == (
        "스태미나",
        "경직",
        "스턴",
    )
    assert result.candidates[0].term_type is TermType.RESOURCE
    assert result.candidates[1].evidence[0].quote == (
        "경직은 피격 직후 짧은 시간 동안 이동과 공격 입력이 제한되는 상태이다."
    )


def test_llm_service_retries_malformed_json_then_accepts_valid_output() -> None:
    valid_output = LLMTermCandidatesOutput(
        candidates=(
            LLMTermCandidate(
                surface="스태미나",
                definition="전투 자원",
                term_type=TermType.RESOURCE,
                tags=("combat",),
                evidence=(LLMEvidence(quote="스태미나는 전투 자원이다."),),
                confidence=0.8,
            ),
        ),
    ).model_dump_json()
    provider = SequencedLLMProvider(
        responses=['{"candidates":[{"surface":"broken"}]}', valid_output],
    )
    service = LLMTermExtractionService(provider, LLMServiceConfig(max_attempts=2))

    result = service.extract_terms(_sample_document("combat_core.md"))

    assert isinstance(result, TermExtractionSuccess)
    assert result.attempts == 2
    assert provider.calls == 2
    assert result.candidates[0].surface == "스태미나"


def test_llm_service_returns_safe_failure_when_provider_json_stays_malformed() -> None:
    provider = SequencedLLMProvider(responses=["{}", "not json"])
    service = LLMTermExtractionService(provider, LLMServiceConfig(max_attempts=2))

    result = service.extract_terms(_sample_document("combat_core.md"))

    assert isinstance(result, AnalysisFailure)
    assert result.code is AnalysisFailureCode.INVALID_JSON
    assert result.provider == "sequenced"
    assert result.attempts == 2


def test_llm_service_returns_safe_failure_when_provider_errors() -> None:
    service = LLMTermExtractionService(BrokenLLMProvider())

    result = service.extract_terms(_sample_document("combat_core.md"))

    assert isinstance(result, AnalysisFailure)
    assert result.code is AnalysisFailureCode.PROVIDER_ERROR
    assert result.message == "provider transport failed"


def test_real_llm_provider_selection_is_disabled_without_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DOC2DIC_LLM_PROVIDER", "openai")
    monkeypatch.delenv("DOC2DIC_LLM_API_KEY", raising=False)
    provider = llm_provider_from_environment()
    service = LLMTermExtractionService(provider)

    result = service.extract_terms(_sample_document("combat_core.md"))

    assert isinstance(provider, DisabledLLMProvider)
    assert isinstance(result, AnalysisFailure)
    assert result.code is AnalysisFailureCode.PROVIDER_DISABLED
    assert "DOC2DIC_LLM_API_KEY" in result.message


def test_real_llm_provider_selection_stays_offline_with_fake_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DOC2DIC_LLM_PROVIDER", "openai")
    monkeypatch.setenv("DOC2DIC_LLM_API_KEY", "fake-non-empty-ci-key")
    provider = llm_provider_from_environment()
    service = LLMTermExtractionService(provider)

    result = service.extract_terms(_sample_document("combat_core.md"))

    assert isinstance(provider, DisabledLLMProvider)
    assert isinstance(result, AnalysisFailure)
    assert result.code is AnalysisFailureCode.PROVIDER_DISABLED
    assert result.message == "real LLM network adapter is not implemented in T16"


def _sample_document(filename: str) -> DocumentContextInput:
    path = ROOT / "samples" / "docs" / filename
    text = path.read_text(encoding="utf-8")
    title = text.splitlines()[0].removeprefix("# ")
    return DocumentContextInput(
        document_id=filename.removesuffix(".md"),
        path=f"samples/docs/{filename}",
        title=title,
        text=text,
    )
