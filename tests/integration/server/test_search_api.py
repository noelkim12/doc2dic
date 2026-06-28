# pyright: basic
"""Integration tests for vector similar-concept search."""

from pathlib import Path
from typing import cast

import pytest

from doc2dic.server.app import create_app
from tests.integration.server.test_concepts_api import request_app


def _seed_concept(app) -> None:
    request_app(
        app,
        "post",
        "/api/concepts",
        {
            "primaryTerm": "Stamina",
            "definition": "Resource spent to enter dungeons.",
            "termType": "resource",
        },
    )


def test_similar_concepts_returns_seeded_concept(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DOC2DIC_EMBEDDING_PROVIDER", "mock")
    app = create_app(project_root=tmp_path)
    _seed_concept(app)

    response = request_app(
        app, "get", "/api/search/similar-concepts?text=stamina"
    )
    body = cast("list[dict]", response.json())

    assert response.status_code == 200
    assert len(body) >= 1
    assert body[0]["concept"]["primaryTerm"] == "Stamina"
    assert 0.0 <= body[0]["similarity"] <= 1.0
    assert "distance" in body[0]


def test_similar_concepts_rejects_empty_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DOC2DIC_EMBEDDING_PROVIDER", "mock")
    app = create_app(project_root=tmp_path)

    response = request_app(
        app, "get", "/api/search/similar-concepts?text=%20%20"
    )
    body = cast("dict", response.json())

    assert response.status_code == 400
    assert body["error"]["code"] == "invalid_query"


def test_similar_concepts_503_when_provider_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DOC2DIC_EMBEDDING_PROVIDER", "disabled")
    app = create_app(project_root=tmp_path)

    response = request_app(
        app, "get", "/api/search/similar-concepts?text=stamina"
    )
    body = cast("dict", response.json())

    assert response.status_code == 503
    assert body["error"]["code"] == "provider_disabled"
