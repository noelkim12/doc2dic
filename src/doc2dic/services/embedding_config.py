"""Project-aware embedding provider resolution."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Final

from doc2dic.services.auth_store import AuthFile, AuthFileError, load_auth_file
from doc2dic.services.embedding_service import (
    EMBEDDING_API_KEY_ENV,
    EMBEDDING_PROVIDER_ENV,
    DeterministicMockEmbeddingProvider,
    DisabledEmbeddingProvider,
    EmbeddingProvider,
    EmbeddingProviderConfig,
    OpenAIEmbeddingProvider,
)
from doc2dic.services.embedding_voyage import (
    DEFAULT_VOYAGE_MODEL,
    VoyageEmbeddingProvider,
)
from doc2dic.storage.repositories import SettingsRepository

if TYPE_CHECKING:
    import sqlite3

EMBEDDING_PROVIDER_SETTING: Final = "embedding.provider"
EMBEDDING_MODEL_SETTING: Final = "embedding.model"
VOYAGE_API_KEY_ENV: Final = "VOYAGE_API_KEY"

_MOCK_PROVIDER_ALIASES: Final = frozenset({"mock", "deterministic_mock"})


def embedding_provider_config_from_project(
    connection: sqlite3.Connection,
) -> EmbeddingProviderConfig:
    """Resolve provider metadata from env, project settings, and auth file."""
    settings = SettingsRepository(connection)
    auth = load_auth_file()
    provider_name = _resolved_provider_name(settings, auth)
    return EmbeddingProviderConfig(
        provider_name=provider_name,
        model=_resolved_model(settings, auth, provider_name),
        api_key=_resolved_api_key(auth, provider_name),
    )


def embedding_provider_from_project(
    connection: sqlite3.Connection,
) -> EmbeddingProvider:
    """Return the project-aware embedding provider for a SQLite connection."""
    try:
        config = embedding_provider_config_from_project(connection)
    except AuthFileError as exc:
        return DisabledEmbeddingProvider(reason=str(exc))
    return _provider_from_config(config)


def embedding_provider_from_settings(
    connection: sqlite3.Connection,
) -> EmbeddingProvider:
    """Alias for callers that name the SQLite source as settings."""
    return embedding_provider_from_project(connection)


def _resolved_provider_name(settings: SettingsRepository, auth: AuthFile) -> str:
    env_provider = _non_empty_env(EMBEDDING_PROVIDER_ENV)
    if env_provider is not None:
        return env_provider
    project_provider = _non_empty_setting(settings, EMBEDDING_PROVIDER_SETTING)
    if project_provider is not None:
        return project_provider
    if auth.embedding.provider != "":
        return auth.embedding.provider
    return "mock"


def _resolved_model(
    settings: SettingsRepository,
    auth: AuthFile,
    provider_name: str,
) -> str:
    project_model = _non_empty_setting(settings, EMBEDDING_MODEL_SETTING)
    if project_model is not None:
        return project_model
    if auth.embedding.provider == provider_name and auth.embedding.model != "":
        return auth.embedding.model
    return _default_model(provider_name)


def _resolved_api_key(auth: AuthFile, provider_name: str) -> str | None:
    match provider_name:
        case "voyage":
            return (
                _non_empty_env(VOYAGE_API_KEY_ENV)
                or _non_empty_env(EMBEDDING_API_KEY_ENV)
                or auth.embedding.api_key_for("voyage")
            )
        case _:
            return _non_empty_env(EMBEDDING_API_KEY_ENV) or auth.embedding.api_key_for(
                provider_name,
            )


def _provider_from_config(config: EmbeddingProviderConfig) -> EmbeddingProvider:
    match config.provider_name:
        case "mock" | "deterministic_mock":
            return DeterministicMockEmbeddingProvider(
                model=config.model or _default_model(config.provider_name),
            )
        case "openai":
            return OpenAIEmbeddingProvider.from_api_key(config.api_key)
        case "voyage":
            return VoyageEmbeddingProvider.from_config(config)
        case "disabled":
            return DisabledEmbeddingProvider(
                model=config.model or _default_model(config.provider_name),
            )
        case unknown:
            reason = f"unsupported embedding provider: {unknown}"
            return DisabledEmbeddingProvider(reason=reason)


def _default_model(provider_name: str) -> str:
    if provider_name in _MOCK_PROVIDER_ALIASES:
        return "mock-embedding-v1"
    match provider_name:
        case "voyage":
            return DEFAULT_VOYAGE_MODEL
        case "openai":
            return "text-embedding-3-large"
        case "disabled":
            return "disabled-embedding"
        case _:
            return ""


def _non_empty_env(name: str) -> str | None:
    value = os.environ.get(name)
    if value is None or value == "":
        return None
    return value


def _non_empty_setting(repository: SettingsRepository, key: str) -> str | None:
    value = repository.get_value(key)
    if value is None or value == "":
        return None
    return value


__all__ = [
    "EMBEDDING_MODEL_SETTING",
    "EMBEDDING_PROVIDER_SETTING",
    "VOYAGE_API_KEY_ENV",
    "embedding_provider_config_from_project",
    "embedding_provider_from_project",
    "embedding_provider_from_settings",
]
