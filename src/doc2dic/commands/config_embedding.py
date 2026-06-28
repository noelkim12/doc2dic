"""Embedding configuration commands and prompts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Annotated, cast

import typer

from doc2dic.commands.project_state import ProjectNotFoundError, discover_project
from doc2dic.services.auth_store import (
    AuthFile,
    AuthFileError,
    default_auth_file_path,
    load_auth_file,
    save_auth_file,
)
from doc2dic.services.embedding_config import (
    EMBEDDING_MODEL_SETTING,
    EMBEDDING_PROVIDER_SETTING,
)
from doc2dic.services.embedding_voyage import DEFAULT_VOYAGE_MODEL
from doc2dic.storage.connection import open_database
from doc2dic.storage.repositories import SettingsRepository

app = typer.Typer(help="Configure embedding provider and credentials.")


class EmbeddingProviderChoice(StrEnum):
    """Supported embedding provider selectors."""

    MOCK = "mock"
    VOYAGE = "voyage"
    OPENAI = "openai"
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class EmbeddingConfig:
    """Parsed embedding configuration input."""

    provider: EmbeddingProviderChoice
    model: str
    api_key: str | None


@dataclass(frozen=True, slots=True)
class ConfigSnapshot:
    """Redacted project configuration snapshot."""

    provider: EmbeddingProviderChoice
    model: str
    auth: AuthFile
    auth_path: Path


@app.callback(invoke_without_command=True)
def embedding(ctx: typer.Context) -> None:
    """Prompt for embedding provider, model, and optional API key."""
    if ctx.invoked_subcommand is not None:
        return
    configure_embedding()


@app.command("use")
def use_embedding(
    provider: Annotated[
        str,
        typer.Argument(help="Embedding provider: mock, voyage, openai, or disabled."),
    ],
    model: Annotated[
        str | None,
        typer.Option("--model", help="Embedding model name."),
    ] = None,
    prompt_api_key: Annotated[
        bool,
        typer.Option(
            "--prompt-api-key",
            help="Prompt for an API key and save it to the global auth file.",
        ),
    ] = False,
) -> None:
    """Configure embedding selection without running the full wizard."""
    selected_provider = _parse_provider(provider)
    selected_model = model or _default_model(selected_provider)
    api_key = _prompt_api_key(selected_provider) if prompt_api_key else None
    _persist_embedding_config(
        EmbeddingConfig(
            provider=selected_provider,
            model=selected_model,
            api_key=api_key,
        ),
    )


@app.command("doctor")
def embedding_doctor() -> None:
    """Show embedding config and redacted credential status."""
    snapshot = _read_config_snapshot()
    key_status = _key_status(snapshot.auth, snapshot.provider)
    typer.echo(f"Embedding provider: {snapshot.provider.value}")
    typer.echo(f"Embedding model: {snapshot.model}")
    typer.echo(f"Auth file: {snapshot.auth_path}")
    typer.echo(f"API key stored: {key_status}")


def show_embedding_config() -> None:
    """Show embedding config values without exposing secrets."""
    snapshot = _read_config_snapshot()
    key_status = _key_status(snapshot.auth, snapshot.provider)
    typer.echo(f"Embedding provider: {snapshot.provider.value}")
    typer.echo(f"Embedding model: {snapshot.model}")
    typer.echo(f"Auth file: {snapshot.auth_path}")
    typer.echo(f"Embedding API key stored: {key_status}")


def configure_embedding() -> None:
    """Run the interactive embedding configuration wizard."""
    snapshot = _read_config_snapshot()
    provider = _prompt_provider(snapshot.provider)
    current_model = snapshot.model
    if provider != snapshot.provider:
        current_model = _default_model(provider)
    model = _prompt_text("Embedding model", current_model)
    api_key = _prompt_api_key(provider)
    _persist_embedding_config(
        EmbeddingConfig(provider=provider, model=model, api_key=api_key),
    )


def prompt_config_target() -> str:
    """Prompt for the root config target."""
    return _prompt_text("Configure [embedding/show]", "embedding")


def _read_config_snapshot() -> ConfigSnapshot:
    try:
        state = discover_project(Path.cwd())
    except ProjectNotFoundError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error
    try:
        auth_path = default_auth_file_path()
        auth = load_auth_file(auth_path)
    except AuthFileError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error
    with open_database(state.db_path) as connection:
        settings = SettingsRepository(connection)
        provider = _configured_provider(settings, auth)
        model = _configured_model(settings, auth, provider)
    return ConfigSnapshot(
        provider=provider,
        model=model,
        auth=auth,
        auth_path=auth_path,
    )


def _persist_embedding_config(config: EmbeddingConfig) -> None:
    try:
        state = discover_project(Path.cwd())
    except ProjectNotFoundError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error
    try:
        auth = load_auth_file(default_auth_file_path())
    except AuthFileError as error:
        typer.echo(str(error), err=True)
        raise typer.Exit(code=1) from error
    with open_database(state.db_path) as connection:
        settings = SettingsRepository(connection)
        settings.set_value(EMBEDDING_PROVIDER_SETTING, config.provider.value)
        settings.set_value(EMBEDDING_MODEL_SETTING, config.model)
    saved_auth = auth.with_embedding(
        provider=config.provider.value,
        model=config.model,
        api_key=config.api_key,
    )
    auth_path = save_auth_file(saved_auth)
    key_status = "unchanged"
    if config.api_key is not None and config.api_key != "":
        key_status = "saved"
    typer.echo(f"Embedding provider: {config.provider.value}")
    typer.echo(f"Embedding model: {config.model}")
    typer.echo(f"Auth file: {auth_path}")
    typer.echo(f"API key: {key_status}")


def _configured_provider(
    settings: SettingsRepository,
    auth: AuthFile,
) -> EmbeddingProviderChoice:
    stored_provider = settings.get_value(EMBEDDING_PROVIDER_SETTING)
    if stored_provider is not None:
        return _parse_provider(stored_provider)
    return _parse_provider(auth.embedding.provider)


def _configured_model(
    settings: SettingsRepository,
    auth: AuthFile,
    provider: EmbeddingProviderChoice,
) -> str:
    stored_model = settings.get_value(EMBEDDING_MODEL_SETTING)
    if stored_model is not None and stored_model != "":
        return stored_model
    if auth.embedding.provider == provider.value and auth.embedding.model != "":
        return auth.embedding.model
    return _default_model(provider)


def _prompt_provider(
    current_provider: EmbeddingProviderChoice,
) -> EmbeddingProviderChoice:
    raw_provider = _prompt_text(
        "Embedding provider (mock/voyage/openai/disabled)",
        current_provider.value,
    )
    return _parse_provider(raw_provider)


def _prompt_api_key(provider: EmbeddingProviderChoice) -> str | None:
    if not _provider_uses_api_key(provider):
        return None
    api_key = _prompt_secret(
        "API key (leave blank to keep existing or skip)",
    )
    if api_key == "":
        return None
    return api_key


def _parse_provider(raw_provider: str) -> EmbeddingProviderChoice:
    normalized = raw_provider.strip().lower()
    try:
        return EmbeddingProviderChoice(normalized)
    except ValueError as error:
        message = "Provider must be one of: mock, voyage, openai, disabled."
        raise typer.BadParameter(message) from error


def _prompt_text(label: str, default: str) -> str:
    return cast("str", typer.prompt(label, default=default, type=str))


def _prompt_secret(label: str) -> str:
    return cast(
        "str",
        typer.prompt(
            label,
            default="",
            hide_input=True,
            show_default=False,
            type=str,
        ),
    )


def _provider_uses_api_key(provider: EmbeddingProviderChoice) -> bool:
    match provider:
        case EmbeddingProviderChoice.MOCK | EmbeddingProviderChoice.DISABLED:
            return False
        case EmbeddingProviderChoice.VOYAGE | EmbeddingProviderChoice.OPENAI:
            return True


def _default_model(provider: EmbeddingProviderChoice) -> str:
    match provider:
        case EmbeddingProviderChoice.MOCK:
            return "mock-embedding-v1"
        case EmbeddingProviderChoice.VOYAGE:
            return DEFAULT_VOYAGE_MODEL
        case EmbeddingProviderChoice.OPENAI:
            return "text-embedding-3-large"
        case EmbeddingProviderChoice.DISABLED:
            return "disabled-embedding"


def _key_status(auth: AuthFile, provider: EmbeddingProviderChoice) -> str:
    if auth.has_embedding_key(provider.value):
        return "yes"
    return "no"
