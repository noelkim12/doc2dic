"""Global auth file storage for local provider credentials."""

from __future__ import annotations

import os
from pathlib import Path
from typing import ClassVar, Final

from pydantic import BaseModel, ConfigDict, Field, ValidationError

AUTH_FILE_ENV: Final = "DOC2DIC_AUTH_FILE"
AUTH_FILE_VERSION: Final = 1
DEFAULT_AUTH_FILENAME: Final = "auth.json"
DEFAULT_CONFIG_DIR_NAME: Final = ".config"
APP_CONFIG_DIR_NAME: Final = "doc2dic"


class AuthFileError(RuntimeError):
    """Raised when the auth file cannot be parsed safely."""


class EmbeddingAuth(BaseModel):
    """Stored embedding auth metadata and provider credentials."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    provider: str = "mock"
    model: str = "mock-embedding-v1"
    api_keys: dict[str, str] = Field(default_factory=dict)

    def api_key_for(self, provider: str) -> str | None:
        """Return the stored API key for a provider, if one exists."""
        key = self.api_keys.get(provider)
        if key is None or key == "":
            return None
        return key


class AuthFile(BaseModel):
    """Versioned global auth file schema."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")

    version: int = AUTH_FILE_VERSION
    embedding: EmbeddingAuth = Field(default_factory=EmbeddingAuth)

    def with_embedding(
        self,
        *,
        provider: str,
        model: str,
        api_key: str | None,
    ) -> AuthFile:
        """Return a copy with embedding provider metadata and optional key."""
        api_keys = dict(self.embedding.api_keys)
        if api_key is not None and api_key != "":
            api_keys[provider] = api_key
        return AuthFile(
            version=AUTH_FILE_VERSION,
            embedding=EmbeddingAuth(
                provider=provider,
                model=model,
                api_keys=api_keys,
            ),
        )

    def has_embedding_key(self, provider: str) -> bool:
        """Return whether a provider key is stored without exposing it."""
        return self.embedding.api_key_for(provider) is not None


def default_auth_file_path() -> Path:
    """Return the cross-platform auth file path."""
    override = os.environ.get(AUTH_FILE_ENV)
    if override is not None and override != "":
        return Path(override).expanduser()
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata is not None and appdata != "":
            return (
                Path(appdata)
                / DEFAULT_CONFIG_DIR_NAME
                / APP_CONFIG_DIR_NAME
                / DEFAULT_AUTH_FILENAME
            )
        return (
            Path.home()
            / "AppData"
            / "Roaming"
            / DEFAULT_CONFIG_DIR_NAME
            / APP_CONFIG_DIR_NAME
            / DEFAULT_AUTH_FILENAME
        )
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config_home is not None and xdg_config_home != "":
        return Path(xdg_config_home) / APP_CONFIG_DIR_NAME / DEFAULT_AUTH_FILENAME
    return (
        Path.home()
        / DEFAULT_CONFIG_DIR_NAME
        / APP_CONFIG_DIR_NAME
        / DEFAULT_AUTH_FILENAME
    )


def load_auth_file(path: Path | None = None) -> AuthFile:
    """Load auth metadata, returning defaults when the file is absent."""
    auth_path = path or default_auth_file_path()
    if not auth_path.exists():
        return AuthFile()
    try:
        return AuthFile.model_validate_json(auth_path.read_text(encoding="utf-8"))
    except ValidationError as exc:
        msg = f"Auth file is invalid: {auth_path}"
        raise AuthFileError(msg) from exc


def save_auth_file(auth: AuthFile, path: Path | None = None) -> Path:
    """Persist auth metadata and restrict POSIX file permissions."""
    auth_path = path or default_auth_file_path()
    auth_path.parent.mkdir(parents=True, exist_ok=True)
    _ = auth_path.write_text(auth.model_dump_json(indent=2) + "\n", encoding="utf-8")
    if os.name != "nt":
        _ = auth_path.chmod(0o600)
    return auth_path


__all__ = [
    "AUTH_FILE_ENV",
    "AuthFile",
    "AuthFileError",
    "EmbeddingAuth",
    "default_auth_file_path",
    "load_auth_file",
    "save_auth_file",
]
