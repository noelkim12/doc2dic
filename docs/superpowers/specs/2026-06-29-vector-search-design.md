# Vector Search for Web Frontend

Date: 2026-06-29
Status: Approved (design)

## Problem

The web frontend (`web/`, React + react-router) lets users browse the glossary
by exact term, but there is no way to find concepts by **meaning**. A user who
types a phrase or a near-synonym cannot discover the glossary terms that are
semantically closest to it.

The backend already ships most of the machinery for this — an embedding service
(`embedding_service.py`, with a deterministic mock provider and a Voyage
provider), a vector store (`vector_store.py` / `vector_backend.py`), and an
embeddings repository that ties stored vectors back to concepts. But the HTTP
seam is unfinished: `GET /api/search/similar-concepts?text=...`
(`routes_search.py`) is a stub that returns `501 Not Implemented`. The FE has a
matching `apiClient.searchSimilarConcepts(text)` function, but nothing calls it
and no page exposes it.

## Goals

- Add a **Vector Search** tab/page to the web frontend. Selecting it switches
  the main area to an input form with a **Search** button.
- On search, send the typed text to the backend, which embeds it with the
  pre-configured embedding model, runs a vector (nearest-neighbour) search over
  stored concept embeddings, and returns the closest concepts.
- Show results as a ranked list with a **similarity %** per item. Clicking a
  result navigates to that concept's glossary detail (`/glossary/:id`).
- Implement the work **end-to-end**: fill the backend stub *and* build the FE.

## Non-Goals (YAGNI)

- **Reranking** (Voyage `rerank-2.5`). Deferred to Phase 2 — see the dedicated
  section below. The endpoint is structured so a rerank stage can slot in later
  without reshaping the response.
- User-adjustable Top-K, search history, debounced as-you-type search.
- Searching owner types other than concepts (the embeddings repository can hold
  `term_candidate` etc.; this feature only surfaces `concept` owners).
- Changing how concept embeddings are *indexed* — this feature only *reads* the
  existing vector index.

## Data Flow

```
[Vector Search page]  text input + [Search] button
        │  GET /api/search/similar-concepts?text=...
        ▼
[routes_search.py]  validate text (non-empty, length-bounded)
        → embedding_provider_from_project(db)            # pre-configured model
        → EmbeddingService(provider).embed_texts((text,), QUERY)
        → VectorStore(db).query_top_k(vector, top_k=CANDIDATE_LIMIT)
        → for each VectorMatch: get_embedding(embedding_id)
              → owner_type == concept → get_concept(owner_id)   # skip others
        → similarity = 1 / (1 + distance)
        ▼
response: [{ concept, distance, similarity }]  ordered by similarity desc, ≤10
```

## Backend Design (`src/doc2dic/server/`)

### Endpoint

Replace the stub in `routes_search.py`:

```python
@router.get("/similar-concepts")
def search_similar_concepts(text: str, database: DatabaseDep) -> ...:
```

Behaviour:

1. **Validate** `text`: strip whitespace; if empty → `400`; if longer than
   `MAX_QUERY_CHARS` (2000) → `400`. Use the existing `error_response` helper.
2. **Embed** the query: resolve the provider via
   `embedding_provider_from_project(database)`, then
   `EmbeddingService(provider).embed_texts((text,), input_type=QUERY)`.
   - On `EmbeddingFailure` (provider disabled / provider error / invalid
     dimension) → `503` with a safe envelope built from the failure `code` and
     `message`.
3. **Vector search**: `VectorStore(database).query_top_k(vector=values,
   top_k=CANDIDATE_LIMIT)`.
   - If `result.enabled is False` (sqlite-vec missing, not indexed, dimension
     mismatch) → `503` `vector_search_unavailable` carrying `result.reason`.
4. **Resolve concepts**: for each `VectorMatch`, look up the `Embedding` via the
   embeddings repository; keep only `owner_type == concept`; load the `Concept`
   via the glossary service; **skip** matches whose concept is missing/deleted
   or whose owner is not a concept.
5. **Score & shape**: `similarity = 1.0 / (1.0 + distance)`. Return the matches
   ordered by similarity descending, truncated to `RESULT_LIMIT` (10).

### Ranking seam (Phase 2 readiness)

`CANDIDATE_LIMIT` (1st-stage retrieval count) and `RESULT_LIMIT` (returned
count) are **distinct named constants**. For the MVP `CANDIDATE_LIMIT == 10 ==
RESULT_LIMIT` (vector order is the final order). The concept-resolution and
truncation logic lives in a small helper (e.g. `_rank_similar_concepts`) so a
future reranking pass can widen `CANDIDATE_LIMIT` (e.g. 50) and re-order the
candidates before truncating to `RESULT_LIMIT`, without touching the route
signature or the response schema.

### Response payload

New Pydantic payload reusing the existing `ConceptPayload`:

```python
class SimilarConceptMatch(BaseModel):
    concept: ConceptPayload
    distance: float
    similarity: float          # 1 / (1 + distance), 0..1
```

Endpoint returns `tuple[SimilarConceptMatch, ...]`.

### Error contract

| Situation                         | Status | Code / body                          |
| --------------------------------- | ------ | ------------------------------------ |
| Empty / whitespace `text`         | 400    | `invalid_query`                      |
| `text` too long                   | 400    | `invalid_query`                      |
| Embedding provider disabled/error | 503    | from `EmbeddingFailure.code`         |
| Vector search not available       | 503    | `vector_search_unavailable` + reason |
| No matches                        | 200    | `[]`                                 |

## Frontend Design (`web/src/`)

### Routing & navigation

- `app/layout.tsx`: add `{ to: "/search", label: "Vector Search" }` to
  `NAV_ITEMS` and register a `<Route path="search" element={<SearchPage />} />`.

### Page — `app/search/page.tsx` (new)

- Single-column page following the existing `page-header` pattern (not
  MasterDetail — there is no master list to keep visible).
- A small form: a text input (multi-line `textarea` acceptable) + a **Search**
  button. The button is **disabled when the trimmed input is empty** (this
  pre-empts the backend `400`).
- On submit, store the submitted text in state and drive a
  `useQuery` keyed on that text, `enabled` only when non-empty. (A query, not a
  mutation, so repeat searches are cached.)
- States via existing shared components: `Loading`, `ErrorState` (with the
  backend message — e.g. the `503` reason so the user learns embeddings aren't
  indexed), and `EmptyState` ("No similar terms found.") when results are empty.

### Component — `components/search/SimilarConceptList.tsx` (new)

- Renders the ranked matches as cards: **rank number**, primary term, a short
  definition excerpt, and a **similarity badge** showing `Math.round(similarity
  * 100)%`. Reuse the existing badge styling (`ConfidenceBadge` or equivalent).
- Clicking a card calls `navigate('/glossary/' + concept.id)`.

### Types & client

- `lib/types.ts`: add `SimilarConceptMatch { concept: Concept; distance:
  number; similarity: number }`.
- `lib/api.ts`: change `searchSimilarConcepts`'s return type from
  `readonly Concept[]` to `readonly SimilarConceptMatch[]` (the URL is
  unchanged).
- `lib/queries.ts`: add `searchQueries.similar(text)` returning `queryOptions`
  keyed on the text.

## Testing

### Backend (pytest)

- Success: with the deterministic mock provider and a seeded vector index,
  the endpoint returns matches ordered by similarity descending, capped at 10,
  each carrying `distance` and `similarity`.
- `503` when the vector store reports `enabled=False`.
- `503` when embedding returns an `EmbeddingFailure`.
- `400` on empty/whitespace text.
- Matches whose owner concept is missing/non-concept are skipped, not errored.

Reuse the existing embedding/vector fixtures (see
`tests/unit/storage/test_vector_store.py` and
`tests/unit/services/test_embedding_service.py`) and the FastAPI test client
pattern used by other route tests.

### Frontend (vitest + Testing Library)

- The form renders; the Search button is disabled until text is entered.
- Submitting calls `apiClient.searchSimilarConcepts` (mocked) and renders the
  result cards with the similarity %.
- Error state renders the backend message; empty result renders the empty
  state.

## Phase 2 (deferred): Voyage reranker

Two-stage retrieval to lift top-k precision:

```
text → embed → VectorStore.query_top_k(CANDIDATE_LIMIT = 50)   # widen recall
     → rerank-2.5(query=text, documents=[candidate definitions])
     → take RESULT_LIMIT = 10                                   # precision
```

Voyage rerankers (`rerank-2.5` / `rerank-2.5-lite`, released 2025-08-11): 32K
context, multilingual (good fit for Korean game-design terms), token-based
pricing with a 200M-token free tier per account. This needs a new rerank
provider seam mirroring `embedding_voyage.py` (REST client + config + offline
mock so tests/offline runs stay deterministic). Deferred because the precision
gain depends on glossary scale and on embeddings actually being indexed —
neither validated yet. The MVP's `CANDIDATE_LIMIT` / `RESULT_LIMIT` split and
the `_rank_similar_concepts` helper are the seam this slots into.
