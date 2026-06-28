# Vector Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Vector Search page to the web frontend that embeds a typed query, runs nearest-neighbour search over stored concept embeddings, and shows the closest glossary terms ranked by similarity.

**Architecture:** Fill the stubbed `GET /api/search/similar-concepts?text=` endpoint to embed the query (QUERY mode) → `VectorStore.query_top_k` → resolve each `VectorMatch.embedding_id` back to its `Concept` → return `{concept, distance, similarity}` ordered by similarity. The FE adds a `/search` route with an input form and a ranked result list whose cards link to `/glossary/:id`.

**Tech Stack:** Backend — Python 3.12+, FastAPI, sqlite3, existing embedding/vector services. Frontend — React 19, react-router-dom 7, @tanstack/react-query 5, TypeScript (strict), vitest + Testing Library.

## ⚠️ Execution base (read before starting)

This plan targets the embedding API in the **main working copy**
(`embedding_config.embedding_provider_from_project`,
`EmbeddingService.embed_texts(..., input_type=EmbeddingInputType.QUERY)`,
`EmbeddingOwnerType`). Those live in **uncommitted** files in the main checkout
and are **absent** from the `worktree-vector-search` worktree (which branched
from committed HEAD). **Do not execute Task 1 in the worktree as-is** — its
imports will not resolve. Execute the backend task where that infrastructure
exists (main checkout, or a worktree rebased onto a commit that includes it).
The frontend tasks (2, 3) are independent of that infrastructure and run
anywhere. The user is resolving the execution-base question separately.

## Global Constraints

- **Endpoint URL is frozen:** `GET /api/search/similar-concepts?text=...`. Do not change the path or query param name.
- **Error envelope:** every error response is `{"error": {"code": <str>, "message": <str>}}` built via `doc2dic.server.errors.error_response(status_code, code, message)`.
- **Similarity formula:** `similarity = 1.0 / (1.0 + distance)` (range 0..1).
- **Result cap:** return at most 10 concepts (`RESULT_LIMIT = 10`).
- **No new dependencies** in either `pyproject.toml` or `web/package.json`.
- **Frontend props are `readonly`;** follow existing component style (default-exported function components, shared `Loading`/`ErrorState`/`EmptyState`).
- **Frontend tests** live flat in `web/tests/*.test.tsx` (not co-located).
- **Commits** use Conventional Commits and end with the trailer:
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

### Task 1: Backend — implement `similar-concepts` endpoint

**Files:**
- Modify: `src/doc2dic/server/routes_search.py` (replace the `search_similar_concepts` stub; keep the `search_concepts` stub untouched)
- Test: `tests/integration/server/test_search_api.py` (create)

**Interfaces:**
- Consumes:
  - `embedding_provider_from_project(connection: sqlite3.Connection) -> EmbeddingProvider` (`services/embedding_config.py`)
  - `EmbeddingService(provider).embed_texts(texts: tuple[str, ...], input_type: EmbeddingInputType = DOCUMENT) -> EmbeddingResult`; on success `EmbeddingSuccess.embeddings[0].values: tuple[float, ...]`; on failure `EmbeddingFailure(code: EmbeddingFailureCode, message: str, provider: str)` (`services/embedding_service.py`)
  - `EmbeddingInputType.QUERY` (`services/embedding_service.py`)
  - `VectorStore(connection).query_top_k(*, vector, top_k) -> VectorQueryResult(enabled: bool, reason: str, matches: tuple[VectorMatch, ...])`; `VectorMatch(embedding_id: int, distance: float)` (`storage/vector_store.py`, `storage/vector_types.py`)
  - `EmbeddingRepository(connection).get_embedding(embedding_id: int) -> Embedding | None`; `Embedding.owner_type: EmbeddingOwnerType`, `Embedding.owner_id: str`; `EmbeddingOwnerType.CONCEPT` (`storage/repositories/embeddings.py`, `domain/embedding.py`)
  - `GlossaryService(database, ProjectGlossaryEmbeddingIndexer(database)).get_concept(id: str) -> Concept` (raises `GlossaryItemNotFoundError`) (`services/glossary_service.py`)
  - `ConceptPayload`, `_concept_payload(concept) -> ConceptPayload`, `DatabaseDep` (`server/routes_concepts.py`, `server/dependencies.py`)
  - `error_response(status_code, code, message) -> JSONResponse` (`server/errors.py`)
- Produces (consumed by the FE contract): `GET /api/search/similar-concepts?text=` returns `200` with a JSON array of `{"concept": <ConceptPayload camelCase>, "distance": number, "similarity": number}`; `400` `invalid_query`; `503` with the embedding failure code or `vector_search_unavailable`.

- [ ] **Step 1: Write the failing test**

Create `tests/integration/server/test_search_api.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/server/test_search_api.py -v`
Expected: FAIL — `test_similar_concepts_returns_seeded_concept` gets `501` (stub) so the `200` assertion fails; the others also fail against the stub.

- [ ] **Step 3: Write the implementation**

Replace the entire body of `src/doc2dic/server/routes_search.py` with:

```python
"""Search routes for the local API contract."""

import sqlite3

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette import status

from doc2dic.domain.embedding import EmbeddingOwnerType
from doc2dic.server.dependencies import DatabaseDep, get_database
from doc2dic.server.errors import error_response, not_implemented_response
from doc2dic.server.routes_concepts import ConceptPayload, _concept_payload
from doc2dic.services.embedding_config import embedding_provider_from_project
from doc2dic.services.embedding_service import (
    EmbeddingFailure,
    EmbeddingInputType,
    EmbeddingService,
)
from doc2dic.services.glossary_embeddings import ProjectGlossaryEmbeddingIndexer
from doc2dic.services.glossary_service import (
    GlossaryItemNotFoundError,
    GlossaryService,
)
from doc2dic.storage.repositories.embeddings import EmbeddingRepository
from doc2dic.storage.vector_store import VectorStore
from doc2dic.storage.vector_types import VectorMatch

router = APIRouter(
    prefix="/api/search",
    tags=["search"],
    dependencies=[Depends(get_database)],
)

MAX_QUERY_CHARS = 2000
# 1st-stage retrieval width. Equal to RESULT_LIMIT for the MVP; a Phase 2
# reranker widens this and re-orders candidates before truncating to
# RESULT_LIMIT, without changing the response schema.
CANDIDATE_LIMIT = 10
RESULT_LIMIT = 10


class SimilarConceptMatch(BaseModel):
    """One similar-concept hit with its vector distance and similarity."""

    concept: ConceptPayload
    distance: float
    similarity: float


@router.get("/concepts")
def search_concepts(q: str) -> JSONResponse:
    """Return the pending concept search stub."""
    _ = q
    return not_implemented_response()


@router.get("/similar-concepts", response_model=None)
def search_similar_concepts(
    text: str,
    database: DatabaseDep,
) -> tuple[SimilarConceptMatch, ...] | JSONResponse:
    """Return concepts whose embeddings are nearest to the query text."""
    query = text.strip()
    if not query:
        return error_response(
            status.HTTP_400_BAD_REQUEST,
            "invalid_query",
            "Search text must not be empty.",
        )
    if len(query) > MAX_QUERY_CHARS:
        return error_response(
            status.HTTP_400_BAD_REQUEST,
            "invalid_query",
            f"Search text must be at most {MAX_QUERY_CHARS} characters.",
        )

    provider = embedding_provider_from_project(database)
    embed_result = EmbeddingService(provider).embed_texts(
        (query,), input_type=EmbeddingInputType.QUERY
    )
    if isinstance(embed_result, EmbeddingFailure):
        return error_response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            embed_result.code.value,
            embed_result.message,
        )

    vector = embed_result.embeddings[0].values
    query_result = VectorStore(database).query_top_k(
        vector=vector, top_k=CANDIDATE_LIMIT
    )
    if not query_result.enabled:
        return error_response(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "vector_search_unavailable",
            query_result.reason,
        )

    return _rank_similar_concepts(database, query_result.matches)


def _rank_similar_concepts(
    database: sqlite3.Connection,
    matches: tuple[VectorMatch, ...],
) -> tuple[SimilarConceptMatch, ...]:
    """Resolve vector matches to concepts, scored and capped to RESULT_LIMIT."""
    embeddings = EmbeddingRepository(database)
    service = GlossaryService(database, ProjectGlossaryEmbeddingIndexer(database))
    results: list[SimilarConceptMatch] = []
    for match in matches:
        embedding = embeddings.get_embedding(match.embedding_id)
        if embedding is None or embedding.owner_type != EmbeddingOwnerType.CONCEPT:
            continue
        try:
            concept = service.get_concept(embedding.owner_id)
        except GlossaryItemNotFoundError:
            continue
        results.append(
            SimilarConceptMatch(
                concept=_concept_payload(concept),
                distance=match.distance,
                similarity=1.0 / (1.0 + match.distance),
            )
        )
        if len(results) >= RESULT_LIMIT:
            break
    return tuple(results)
```

Notes:
- `_concept_payload` is a same-package internal helper reused here to keep concept serialization DRY (identical shape to `GET /api/concepts`).
- The router keeps its existing `dependencies=[Depends(get_database)]`; `DatabaseDep` resolves to the same per-request connection.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/integration/server/test_search_api.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Run typecheck/lint for the changed module**

Run: `ruff check src/doc2dic/server/routes_search.py && pyright src/doc2dic/server/routes_search.py`
Expected: no errors. (If the repo uses a different lint/type command, run that instead — check `pyproject.toml`.)

- [ ] **Step 6: Commit**

```bash
git add src/doc2dic/server/routes_search.py tests/integration/server/test_search_api.py
git commit -m "$(cat <<'EOF'
feat(server): implement similar-concepts vector search endpoint

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: Frontend — data layer + result list component

**Files:**
- Modify: `web/src/lib/types.ts` (add `SimilarConceptMatch`)
- Modify: `web/src/lib/api.ts` (change `searchSimilarConcepts` return type + import)
- Modify: `web/src/lib/queries.ts` (add `searchQueries`)
- Create: `web/src/components/search/SimilarConceptList.tsx`
- Test: `web/tests/vector-search.test.tsx` (create — component section)

**Interfaces:**
- Consumes: `Concept` (`web/src/lib/types.ts`); `apiClient.searchSimilarConcepts` (`web/src/lib/api.ts`); `queryOptions` (@tanstack/react-query); `useNavigate` (react-router-dom).
- Produces:
  - `SimilarConceptMatch = { readonly concept: Concept; readonly distance: number; readonly similarity: number }`
  - `apiClient.searchSimilarConcepts(text: string): Promise<readonly SimilarConceptMatch[]>`
  - `searchQueries.similar(text: string)` → react-query `queryOptions` (enabled only when `text.trim()` is non-empty)
  - `<SimilarConceptList matches={readonly SimilarConceptMatch[]} />` — renders ranked cards (rank, term, definition, `Math.round(similarity*100)%`), each navigating to `/glossary/:id` on click.

- [ ] **Step 1: Write the failing test**

Create `web/tests/vector-search.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import React from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import type { SimilarConceptMatch } from "../src/lib/types";
import SimilarConceptList from "../src/components/search/SimilarConceptList";

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return { ...actual, useNavigate: () => mockNavigate };
});

const MATCHES: readonly SimilarConceptMatch[] = [
  {
    concept: {
      id: "c_1",
      primaryTerm: "스태미나",
      definition: "A stat resource.",
      termType: "stat",
      status: "active",
      tags: [],
      variants: [],
      createdAt: "2025-01-01T00:00:00Z",
      updatedAt: "2025-01-01T00:00:00Z",
    },
    distance: 0.1,
    similarity: 0.91,
  },
];

describe("SimilarConceptList", () => {
  it("renders rank, term and similarity percent", () => {
    render(
      <MemoryRouter>
        <SimilarConceptList matches={MATCHES} />
      </MemoryRouter>,
    );
    expect(screen.getByText("스태미나")).toBeInTheDocument();
    expect(screen.getByText("91%")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
  });

  it("navigates to glossary detail on click", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <SimilarConceptList matches={MATCHES} />
      </MemoryRouter>,
    );
    await user.click(screen.getByText("스태미나"));
    expect(mockNavigate).toHaveBeenCalledWith("/glossary/c_1");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run tests/vector-search.test.tsx`
Expected: FAIL — module `../src/components/search/SimilarConceptList` and type `SimilarConceptMatch` do not exist.

- [ ] **Step 3: Add the type**

In `web/src/lib/types.ts`, directly after the `Concept` type definition, add:

```ts
export type SimilarConceptMatch = {
  readonly concept: Concept;
  readonly distance: number;
  readonly similarity: number;
};
```

- [ ] **Step 4: Update the API client**

In `web/src/lib/api.ts`, add `SimilarConceptMatch` to the type import block (the `import type { ... } from "./types";` list), then change the method:

```ts
  searchSimilarConcepts(text: string): Promise<readonly SimilarConceptMatch[]> {
    return get(
      `${API_ENDPOINTS.searchSimilarConcepts}?text=${encodeURIComponent(text)}`,
    );
  },
```

- [ ] **Step 5: Add the query options**

In `web/src/lib/queries.ts`, add (after the existing `issueQueries` block):

```ts
export const searchQueries = {
  all: ["search"] as const,
  similar: (text: string) =>
    queryOptions({
      queryKey: [...searchQueries.all, "similar", text] as const,
      queryFn: () => apiClient.searchSimilarConcepts(text),
      enabled: text.trim().length > 0,
    }),
};
```

- [ ] **Step 6: Write the component**

Create `web/src/components/search/SimilarConceptList.tsx`:

```tsx
import { useNavigate } from "react-router-dom";
import type { SimilarConceptMatch } from "../../lib/types";

interface Props {
  readonly matches: readonly SimilarConceptMatch[];
}

export default function SimilarConceptList({ matches }: Props) {
  const navigate = useNavigate();
  return (
    <ol className="similar-list">
      {matches.map((match, index) => (
        <li key={match.concept.id} className="similar-item">
          <button
            type="button"
            className="similar-card"
            onClick={() => navigate(`/glossary/${match.concept.id}`)}
          >
            <span className="similar-rank">{index + 1}</span>
            <span className="similar-term">{match.concept.primaryTerm}</span>
            <span className="similar-definition">
              {match.concept.definition}
            </span>
            <span className="similar-score">
              {Math.round(match.similarity * 100)}%
            </span>
          </button>
        </li>
      ))}
    </ol>
  );
}
```

- [ ] **Step 7: Run test to verify it passes**

Run: `cd web && npx vitest run tests/vector-search.test.tsx`
Expected: PASS (2 tests in the `SimilarConceptList` describe block).

- [ ] **Step 8: Commit**

```bash
git add web/src/lib/types.ts web/src/lib/api.ts web/src/lib/queries.ts \
        web/src/components/search/SimilarConceptList.tsx \
        web/tests/vector-search.test.tsx
git commit -m "$(cat <<'EOF'
feat(web): add similar-concept result list and search data layer

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: Frontend — Vector Search page + navigation

**Files:**
- Create: `web/src/app/search/page.tsx`
- Modify: `web/src/app/layout.tsx` (nav item + route)
- Test: `web/tests/vector-search.test.tsx` (extend — page section)

**Interfaces:**
- Consumes: `searchQueries.similar` (Task 2); `SimilarConceptList` (Task 2); shared `Loading`/`ErrorState`/`EmptyState`; `ApiError` (`web/src/lib/api.ts`); `useQuery` (@tanstack/react-query).
- Produces: a `SearchPage` default export mounted at route `/search`, reachable from a `"Vector Search"` nav link. Search button disabled while the trimmed input is empty; on submit it queries and renders `SimilarConceptList`, with loading/error/empty states.

- [ ] **Step 1: Write the failing test**

Append to `web/tests/vector-search.test.tsx` (add imports at the top of the file alongside the existing ones, and the new `describe` at the end):

```tsx
// --- add to the import section ---
import { waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import SearchPage from "../src/app/search/page";

// --- add after the existing react-router-dom mock ---
const mockSearch = vi.fn();
vi.mock("../src/lib/api", async () => {
  const actual = await vi.importActual("../src/lib/api");
  return {
    ...actual,
    apiClient: {
      ...(actual as Record<string, unknown>).apiClient,
      searchSimilarConcepts: (...args: unknown[]) => mockSearch(...args),
    },
  };
});

function renderPage(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/search"]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

// --- add at the end of the file ---
describe("SearchPage", () => {
  it("disables the Search button when input is empty", () => {
    renderPage(<SearchPage />);
    expect(screen.getByRole("button", { name: "Search" })).toBeDisabled();
  });

  it("shows ranked results with similarity after searching", async () => {
    const user = userEvent.setup();
    mockSearch.mockResolvedValue(MATCHES);
    renderPage(<SearchPage />);

    await user.type(screen.getByLabelText(/search text/i), "stamina");
    await user.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() =>
      expect(screen.getByText("스태미나")).toBeInTheDocument(),
    );
    expect(screen.getByText("91%")).toBeInTheDocument();
    expect(mockSearch).toHaveBeenCalledWith("stamina");
  });

  it("shows the empty state when no results are returned", async () => {
    const user = userEvent.setup();
    mockSearch.mockResolvedValue([]);
    renderPage(<SearchPage />);

    await user.type(screen.getByLabelText(/search text/i), "zzz");
    await user.click(screen.getByRole("button", { name: "Search" }));

    await waitFor(() =>
      expect(screen.getByText(/no similar terms found/i)).toBeInTheDocument(),
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npx vitest run tests/vector-search.test.tsx`
Expected: FAIL — module `../src/app/search/page` does not exist.

- [ ] **Step 3: Write the page**

Create `web/src/app/search/page.tsx`:

```tsx
import { useState } from "react";
import type { FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import SimilarConceptList from "../../components/search/SimilarConceptList";
import Loading from "../../components/shared/Loading";
import ErrorState from "../../components/shared/ErrorState";
import EmptyState from "../../components/shared/EmptyState";
import { searchQueries } from "../../lib/queries";
import { ApiError } from "../../lib/api";

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.body?.message || error.message;
  }
  return error instanceof Error ? error.message : "Search failed";
}

export default function SearchPage() {
  const [text, setText] = useState("");
  const [submitted, setSubmitted] = useState("");

  const query = useQuery(searchQueries.similar(submitted));
  const results = query.data ?? [];
  const hasSubmitted = submitted.length > 0;

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSubmitted(text.trim());
  }

  return (
    <div className="page-search">
      <header className="page-header">
        <h1 className="page-title">Vector Search</h1>
      </header>

      <form className="search-form" onSubmit={handleSubmit}>
        <label htmlFor="search-text">Search text</label>
        <textarea
          id="search-text"
          className="search-input"
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder="Enter a phrase to find semantically similar terms..."
        />
        <button
          className="btn-primary"
          type="submit"
          disabled={text.trim().length === 0}
        >
          Search
        </button>
      </form>

      <section className="search-results" aria-label="Search results">
        {!hasSubmitted ? (
          <EmptyState message="Enter text and search to find similar terms." />
        ) : query.isLoading ? (
          <Loading label="Searching..." />
        ) : query.isError ? (
          <ErrorState
            message={errorMessage(query.error)}
            onRetry={() => query.refetch()}
          />
        ) : results.length === 0 ? (
          <EmptyState message="No similar terms found." />
        ) : (
          <SimilarConceptList matches={results} />
        )}
      </section>
    </div>
  );
}
```

- [ ] **Step 4: Wire navigation and the route**

In `web/src/app/layout.tsx`:

1. Add the import near the other page imports:

```tsx
import SearchPage from "./search/page";
```

2. Add the nav entry to `NAV_ITEMS` (place it after the `graph` entry, before `settings`):

```tsx
  { to: "/search", label: "Vector Search" },
```

3. Register the route inside `<Routes>` (alongside the other top-level routes, e.g. after the `graph` route):

```tsx
          <Route path="search" element={<SearchPage />} />
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd web && npx vitest run tests/vector-search.test.tsx`
Expected: PASS (all `SimilarConceptList` and `SearchPage` tests).

- [ ] **Step 6: Run the full FE checks**

Run: `cd web && npm run typecheck && npx vitest run`
Expected: typecheck clean; full test suite passes (no regressions in `shell.test.tsx`, which asserts nav items).

> Note: `web/tests/shell.test.tsx` checks the nav. If it asserts an exact nav-item count or list, update that expectation to include "Vector Search" in this step.

- [ ] **Step 7: Commit**

```bash
git add web/src/app/search/page.tsx web/src/app/layout.tsx web/tests/vector-search.test.tsx
git commit -m "$(cat <<'EOF'
feat(web): add Vector Search page and navigation

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Optional follow-up (not part of this plan)

- Styling for `.page-search` / `.search-form` / `.similar-*` classes in `web/src/index.css`, matching the existing page/card styling. Functional behaviour does not depend on it.
- Phase 2 reranker (Voyage `rerank-2.5`) per the design doc's deferred section: widen `CANDIDATE_LIMIT`, add a rerank provider seam mirroring `embedding_voyage.py`, re-order candidates inside `_rank_similar_concepts` before the `RESULT_LIMIT` truncation.
