from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest
from tests.integration.voyage_smoke_helper import (
    FAKE_LIVE_VOYAGE_SECRET,
    LiveVoyageReady,
    LiveVoyageSkip,
    format_live_voyage_metadata,
    live_voyage_gate,
    run_live_voyage_smoke,
)

from doc2dic.services.auth_store import AuthFile, save_auth_file

if TYPE_CHECKING:
    import urllib.request
    from pathlib import Path
    from types import TracebackType
    from typing import Self


def test_live_voyage_smoke_gate(capsys: pytest.CaptureFixture[str]) -> None:
    gate = live_voyage_gate()
    match gate:
        case LiveVoyageSkip(reason=reason):
            pytest.skip(reason)
        case LiveVoyageReady(api_key=api_key):
            metadata = run_live_voyage_smoke(api_key=api_key)
            output = format_live_voyage_metadata(metadata)
            _ = sys.stdout.write(f"{output}\n")
            captured = capsys.readouterr()
            assert api_key not in captured.out


def test_voyage_smoke_gate_reports_no_key_when_opted_in_without_credentials(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    empty_auth_path = tmp_path / "auth.json"
    monkeypatch.setenv("DOC2DIC_RUN_LIVE_VOYAGE_TESTS", "1")
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
    monkeypatch.delenv("DOC2DIC_EMBEDDING_API_KEY", raising=False)
    monkeypatch.setenv("DOC2DIC_AUTH_FILE", str(empty_auth_path))

    gate = live_voyage_gate()

    assert gate == LiveVoyageSkip(reason="reason=no_key")


def test_voyage_smoke_gate_accepts_auth_file_key(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    auth_path = tmp_path / "auth.json"
    auth = AuthFile().with_embedding(
        provider="voyage",
        model="voyage-4-large",
        api_key=FAKE_LIVE_VOYAGE_SECRET,
    )
    _ = save_auth_file(auth, auth_path)
    monkeypatch.setenv("DOC2DIC_RUN_LIVE_VOYAGE_TESTS", "1")
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
    monkeypatch.delenv("DOC2DIC_EMBEDDING_API_KEY", raising=False)
    monkeypatch.setenv("DOC2DIC_AUTH_FILE", str(auth_path))

    gate = live_voyage_gate()

    assert gate == LiveVoyageReady(api_key=FAKE_LIVE_VOYAGE_SECRET)


def test_voyage_smoke_metadata_output_redacts_fake_key() -> None:
    metadata = run_live_voyage_smoke(
        api_key=FAKE_LIVE_VOYAGE_SECRET,
        opener=FakeVoyageSmokeOpener(),
    )

    output = format_live_voyage_metadata(metadata)

    assert "status=200" in output
    assert "model=voyage-4-large" in output
    assert "embedding_count=1" in output
    assert "vector_dimension=3" in output
    assert "total_tokens=7" in output
    assert FAKE_LIVE_VOYAGE_SECRET not in output


class FakeVoyageSmokeResponse:
    status: int = 200

    def read(self) -> bytes:
        return (
            b'{"data":[{"embedding":[0.1,0.2,0.3],"index":0}],'
            b'"model":"voyage-4-large","usage":{"total_tokens":7}}'
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        _ = exc_type
        _ = exc
        _ = traceback


class FakeVoyageSmokeOpener:
    def __call__(
        self,
        request: urllib.request.Request,
        /,
        *,
        timeout: float,
    ) -> FakeVoyageSmokeResponse:
        _ = request
        _ = timeout
        return FakeVoyageSmokeResponse()
