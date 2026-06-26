"""LLM provider contracts and deterministic term extraction service."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Final, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from doc2dic.services.document_context_cards import (
    AnalysisContextCards,
    DocumentContextInput,
    bounded_evidence_quote,
    build_context_cards,
)
from doc2dic.services.document_llm_templates import (
    TermTemplate,
    TermType,
    templates_for_document,
)

MOCK_PROVIDER_NAME: Final = "deterministic_mock"
DISABLED_PROVIDER_NAME: Final = "disabled_real_provider"
DEFAULT_MAX_ATTEMPTS: Final = 2
MAX_TAG_CHARS: Final = 64
LLM_API_KEY_ENV: Final = "DOC2DIC_LLM_API_KEY"


class AnalysisFailureCode(StrEnum):
    """Safe provider failure categories for analysis callers."""

    PROVIDER_DISABLED = "provider_disabled"
    PROVIDER_ERROR = "provider_error"
    INVALID_JSON = "invalid_json"


class LLMEvidence(BaseModel):
    """Bounded quote evidence attached to one candidate."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    quote: str = Field(min_length=1, max_length=600)
    section_title: str = Field(default="", max_length=240)


class LLMTermCandidate(BaseModel):
    """Structured term candidate matching the frozen LLM schema."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    surface: str = Field(min_length=1, max_length=160)
    definition: str = Field(min_length=1, max_length=2000)
    term_type: TermType
    tags: tuple[str, ...]
    evidence: tuple[LLMEvidence, ...] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)

    @field_validator("tags")
    @classmethod
    def tags_must_match_schema(cls, tags: tuple[str, ...]) -> tuple[str, ...]:
        """Reject empty, oversized, or duplicate tags."""
        if len(tags) != len(frozenset(tags)):
            msg = "tags must be unique"
            raise ValueError(msg)
        for tag in tags:
            if not 1 <= len(tag) <= MAX_TAG_CHARS:
                msg = "tags must be 1-64 characters"
                raise ValueError(msg)
        return tags


class LLMTermCandidatesOutput(BaseModel):
    """Top-level structured output for candidate extraction."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    candidates: tuple[LLMTermCandidate, ...]


@dataclass(frozen=True, slots=True)
class AnalysisFailure:
    """Safe failure record without partial review or glossary mutations."""

    code: AnalysisFailureCode
    message: str
    provider: str
    attempts: int


@dataclass(frozen=True, slots=True)
class TermExtractionSuccess:
    """Accepted term extraction result after structured validation."""

    provider: str
    attempts: int
    candidates: tuple[LLMTermCandidate, ...]


type TermExtractionResult = TermExtractionSuccess | AnalysisFailure


class LLMProvider(Protocol):
    """Provider seam for structured term candidate JSON."""

    @property
    def provider_name(self) -> str:
        """Stable provider identifier."""
        ...

    def extract_term_candidates(self, context: AnalysisContextCards) -> str:
        """Return raw JSON following LLMTermCandidatesOutput."""
        ...


class LLMProviderError(RuntimeError):
    """Raised when a provider cannot produce candidate JSON."""


class ProviderDisabledError(LLMProviderError):
    """Raised by real adapters when credentials or implementation are disabled."""


@dataclass(frozen=True, slots=True)
class LLMServiceConfig:
    """Retry settings for structured LLM output validation."""

    max_attempts: int = DEFAULT_MAX_ATTEMPTS


DEFAULT_LLM_SERVICE_CONFIG: Final = LLMServiceConfig()



class LLMTermExtractionService:
    """Validate provider JSON before exposing accepted candidates."""

    def __init__(
        self,
        provider: LLMProvider,
        config: LLMServiceConfig = DEFAULT_LLM_SERVICE_CONFIG,
    ) -> None:
        """Store the provider and bounded retry settings."""
        self._provider: LLMProvider
        self._provider = provider
        self._config: LLMServiceConfig
        self._config = config

    def extract_terms(self, document: DocumentContextInput) -> TermExtractionResult:
        """Extract validated term candidates from one document context."""
        context = build_context_cards(document)
        attempts = max(1, self._config.max_attempts)
        last_error = "provider returned invalid structured output"
        for attempt in range(1, attempts + 1):
            try:
                payload = self._provider.extract_term_candidates(context)
                parsed = LLMTermCandidatesOutput.model_validate_json(payload)
            except ProviderDisabledError as exc:
                return AnalysisFailure(
                    code=AnalysisFailureCode.PROVIDER_DISABLED,
                    message=str(exc),
                    provider=self._provider.provider_name,
                    attempts=attempt,
                )
            except LLMProviderError as exc:
                return AnalysisFailure(
                    code=AnalysisFailureCode.PROVIDER_ERROR,
                    message=str(exc),
                    provider=self._provider.provider_name,
                    attempts=attempt,
                )
            except ValidationError as exc:
                last_error = str(exc).splitlines()[0]
                continue
            return TermExtractionSuccess(
                provider=self._provider.provider_name,
                attempts=attempt,
                candidates=parsed.candidates,
            )
        return AnalysisFailure(
            code=AnalysisFailureCode.INVALID_JSON,
            message=last_error,
            provider=self._provider.provider_name,
            attempts=attempts,
        )


class DeterministicMockLLMProvider:
    """Fixture-truth mock extractor with stable Korean candidate output."""

    @property
    def provider_name(self) -> str:
        """Stable provider identifier."""
        return MOCK_PROVIDER_NAME

    def extract_term_candidates(self, context: AnalysisContextCards) -> str:
        """Return schema-shaped JSON derived from known sample text."""
        candidates = tuple(
            _candidate_from_template(template, context.document.title)
            for template in templates_for_document(context.document)
        )
        return LLMTermCandidatesOutput(candidates=candidates).model_dump_json()


@dataclass(frozen=True, slots=True)
class DisabledLLMProvider:
    """Offline-safe stand-in for future real LLM adapters."""

    reason: str = "LLM provider is disabled; set a supported adapter in a later task."
    provider_name: str = DISABLED_PROVIDER_NAME

    def extract_term_candidates(self, context: AnalysisContextCards) -> str:
        """Reject extraction without making any network call."""
        _ = context
        raise ProviderDisabledError(self.reason)


class OpenAILLMProvider(DisabledLLMProvider):
    """Skeletal real adapter that remains disabled for offline MVP tests."""

    provider_name: str = "openai_disabled"

    @classmethod
    def from_environment(cls) -> OpenAILLMProvider | DisabledLLMProvider:
        """Select a disabled adapter without requiring SDKs or network access."""
        api_key = os.environ.get(LLM_API_KEY_ENV)
        if api_key is None or api_key == "":
            return DisabledLLMProvider(reason=f"{LLM_API_KEY_ENV} is not configured")
        return cls(reason="real LLM network adapter is not implemented in T16")


def llm_provider_from_environment() -> LLMProvider:
    """Return the configured LLM provider without requiring external keys."""
    provider_name = os.environ.get("DOC2DIC_LLM_PROVIDER", MOCK_PROVIDER_NAME)
    match provider_name:
        case "mock" | "deterministic_mock":
            return DeterministicMockLLMProvider()
        case "openai":
            return OpenAILLMProvider.from_environment()
        case "disabled":
            return DisabledLLMProvider()
        case unknown:
            return DisabledLLMProvider(reason=f"unsupported LLM provider: {unknown}")


def _candidate_from_template(
    template: TermTemplate,
    section_title: str,
) -> LLMTermCandidate:
    return LLMTermCandidate(
        surface=template.surface,
        definition=template.definition,
        term_type=template.term_type,
        tags=template.tags,
        evidence=(
            LLMEvidence(
                quote=bounded_evidence_quote(template.quote),
                section_title=section_title,
            ),
        ),
        confidence=1.0,
    )


__all__ = [
    "DEFAULT_LLM_SERVICE_CONFIG",
    "AnalysisFailure",
    "AnalysisFailureCode",
    "DeterministicMockLLMProvider",
    "DisabledLLMProvider",
    "LLMEvidence",
    "LLMProvider",
    "LLMProviderError",
    "LLMServiceConfig",
    "LLMTermCandidate",
    "LLMTermCandidatesOutput",
    "LLMTermExtractionService",
    "OpenAILLMProvider",
    "ProviderDisabledError",
    "TermExtractionResult",
    "TermExtractionSuccess",
    "TermType",
    "llm_provider_from_environment",
]
