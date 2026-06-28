# 3-Pane Master-Detail Layout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the web frontend's list→detail tabs (Glossary, Documents, Review) into a unified 3-bay layout (nav rail + master list + right detail pane) with URL-driven selection.

**Architecture:** Visual 3-bay = app nav (shell column 1) + master list (main, center) + detail (main, right). The app shell keeps its `nav | main` grid; inside `main`, each list-detail tab renders `list | <Outlet/>` via react-router nested routes, so selection lives in the URL (`/glossary/:conceptId`, `/documents/:documentId`, `/review/:issueId`). A shared `MasterDetail` component provides the `list | Outlet` grid; the index route renders an `EmptyState` placeholder in the right pane.

**Tech Stack:** React 18, react-router-dom v6, @tanstack/react-query, Vitest + @testing-library/react, plain CSS (`web/src/index.css`).

## Global Constraints

- All paths are relative to the repo root; frontend code lives under `web/`.
- Run all test/build commands from the `web/` directory.
- Test runner: `npx vitest run <file>` (single file) / `npx vitest run` (all).
- Reuse existing shared components: `EmptyState`, `ErrorState`, `Loading`, `StatusBadge`.
- Reuse existing query factories: `conceptQueries.detail(id)`, `documentQueries.detail(id)`, `issueQueries.detail(id)` — do NOT add new endpoints.
- Selected-row highlight reuses the existing `.data-row.selected` CSS.
- Keep the existing simpler layout pattern: detail pane scrolls via `max-height: calc(100vh - 160px); overflow-y: auto` (matches current `.review-detail-panel`), NOT a full-height flex rewrite.

---

### Task 1: Shared `MasterDetail` component + grid CSS

**Files:**
- Create: `web/src/components/shared/MasterDetail.tsx`
- Modify: `web/src/index.css` (add `.master-detail`, `.md-list`, `.md-detail`, responsive block near the existing `.documents-layout` block at line ~677)
- Test: `web/tests/master-detail.test.tsx` (create)

**Interfaces:**
- Produces: `MasterDetail` — default export, props `{ list: ReactNode }`. Renders `<div class="master-detail"><div class="md-list">{list}</div><div class="md-detail"><Outlet/></div></div>`. Must be rendered inside a react-router route tree (uses `<Outlet/>`).

- [ ] **Step 1: Write the failing test**

```tsx
// web/tests/master-detail.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import MasterDetail from "../src/components/shared/MasterDetail";

describe("MasterDetail", () => {
  it("renders the list slot and the routed detail via Outlet", () => {
    render(
      <MemoryRouter initialEntries={["/x/1"]}>
        <Routes>
          <Route path="/x" element={<MasterDetail list={<div>LIST</div>} />}>
            <Route path=":id" element={<div>DETAIL</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText("LIST")).toBeInTheDocument();
    expect(screen.getByText("DETAIL")).toBeInTheDocument();
  });

  it("renders the index placeholder when no child route matches", () => {
    render(
      <MemoryRouter initialEntries={["/x"]}>
        <Routes>
          <Route path="/x" element={<MasterDetail list={<div>LIST</div>} />}>
            <Route index element={<div>PLACEHOLDER</div>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText("PLACEHOLDER")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run tests/master-detail.test.tsx`
Expected: FAIL — cannot resolve `../src/components/shared/MasterDetail`.

- [ ] **Step 3: Write the component**

```tsx
// web/src/components/shared/MasterDetail.tsx
import type { ReactNode } from "react";
import { Outlet } from "react-router-dom";

interface Props {
  readonly list: ReactNode;
}

/**
 * Three-pane master-detail shell. Renders the master `list` on the left and the
 * routed detail pane on the right via <Outlet/>. The right pane's content is
 * driven entirely by the nested route (`:id` panel or index placeholder), so the
 * selection is reflected in the URL.
 */
export default function MasterDetail({ list }: Props) {
  return (
    <div className="master-detail">
      <div className="md-list">{list}</div>
      <div className="md-detail">
        <Outlet />
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Add CSS**

Add after the `.documents-layout { ... }` block (around line 682) in `web/src/index.css`:

```css
/* ── Shared 3-pane master-detail ── */

.master-detail {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(360px, 0.85fr);
  gap: var(--space-lg);
  min-height: 0;
}

.md-list {
  overflow-x: auto;
}

.md-detail {
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
  max-height: calc(100vh - 160px);
  overflow-y: auto;
  padding-right: var(--space-sm);
}

@media (max-width: 1024px) {
  .master-detail {
    grid-template-columns: 1fr;
  }
  .md-detail {
    max-height: none;
  }
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `npx vitest run tests/master-detail.test.tsx`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add web/src/components/shared/MasterDetail.tsx web/src/index.css web/tests/master-detail.test.tsx
git commit -m "feat(web): add shared MasterDetail 3-pane layout"
```

---

### Task 2: Glossary 3-pane (nested route, URL-driven detail)

**Files:**
- Modify: `web/src/app/glossary/page.tsx` (becomes master container)
- Modify: `web/src/app/glossary/[conceptId]/page.tsx` (becomes right-pane panel, drop full-page header + back link)
- Modify: `web/src/components/glossary/ConceptTable.tsx` (add `selectedId` highlight)
- Modify: `web/src/app/layout.tsx` (nest the glossary routes)
- Test: `web/tests/glossary.test.tsx` (update existing expectations)

**Interfaces:**
- Consumes: `MasterDetail` from Task 1; `conceptQueries.detail(id)`, `conceptQueries.list()`, `useCreateConcept`, `usePatchConcept`, `useCreateVariant`.
- Produces: `GlossaryPage` (default export) renders header + optional `ConceptForm` + `<MasterDetail list={<ConceptTable .../>} />`. `ConceptDetailPage` (default export) is the right-pane panel reading `:conceptId` from `useParams`. `ConceptTable` gains optional prop `selectedId?: string`.

- [ ] **Step 1: Update ConceptTable test for selected highlight (failing test)**

Append to the `describe("ConceptTable", ...)` block in `web/tests/glossary.test.tsx`:

```tsx
  it("marks the selected row with the selected class", () => {
    const { container } = renderWithProviders(
      <ConceptTable concepts={MOCK_CONCEPTS} selectedId="c_1" />,
    );
    const selected = container.querySelector(".data-row.selected");
    expect(selected).not.toBeNull();
    expect(selected).toHaveTextContent("스태미나");
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run tests/glossary.test.tsx -t "marks the selected row"`
Expected: FAIL — no element matches `.data-row.selected` (prop not supported yet).

- [ ] **Step 3: Add `selectedId` to ConceptTable**

In `web/src/components/glossary/ConceptTable.tsx`, update the props interface and the row className:

```tsx
interface Props {
  concepts: readonly Concept[];
  onSelect?: (id: string) => void;
  selectedId?: string;
}

export default function ConceptTable({ concepts, onSelect, selectedId }: Props) {
```

Change the row `<tr>` className from:

```tsx
                className={`data-row ${onSelect ? "clickable" : ""}`}
```

to:

```tsx
                className={`data-row ${onSelect ? "clickable" : ""} ${
                  selectedId === c.id ? "selected" : ""
                }`}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run tests/glossary.test.tsx -t "marks the selected row"`
Expected: PASS.

- [ ] **Step 5: Convert GlossaryPage into the master container**

Replace the body of `web/src/app/glossary/page.tsx` with:

```tsx
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import ConceptTable from "../../components/glossary/ConceptTable";
import ConceptForm from "../../components/glossary/ConceptForm";
import MasterDetail from "../../components/shared/MasterDetail";
import Loading from "../../components/shared/Loading";
import ErrorState from "../../components/shared/ErrorState";
import EmptyState from "../../components/shared/EmptyState";
import { conceptQueries, useCreateConcept } from "../../lib/queries";
import { ApiError } from "../../lib/api";

export default function GlossaryPage() {
  const navigate = useNavigate();
  const { conceptId } = useParams<{ conceptId: string }>();
  const [showCreate, setShowCreate] = useState(false);

  const listQuery = useQuery(conceptQueries.list());
  const createMutation = useCreateConcept();

  function handleSelect(id: string) {
    navigate(`/glossary/${id}`);
  }

  function mutationApiError(err: unknown): ApiError | null {
    return err instanceof ApiError ? err : null;
  }

  const listContent = listQuery.isLoading ? (
    <Loading label="Loading concepts..." />
  ) : listQuery.isError ? (
    <ErrorState
      message={listQuery.error.message || "Failed to load concepts"}
      onRetry={() => listQuery.refetch()}
    />
  ) : listQuery.data?.length === 0 ? (
    <EmptyState message="No concepts yet. Create your first term!" />
  ) : (
    <ConceptTable
      concepts={listQuery.data ?? []}
      onSelect={handleSelect}
      selectedId={conceptId}
    />
  );

  return (
    <div className="page-glossary">
      <header className="page-header">
        <h1 className="page-title">Glossary</h1>
        <button
          className="btn-primary btn-sm"
          type="button"
          onClick={() => setShowCreate((v) => !v)}
          aria-expanded={showCreate}
        >
          {showCreate ? "Cancel" : "New Concept"}
        </button>
      </header>

      {showCreate && (
        <section className="create-section" aria-label="Create concept">
          <ConceptForm
            onSubmit={(data) => {
              void createMutation.mutateAsync(
                data as Parameters<NonNullable<typeof createMutation.mutate>>[0],
              );
            }}
            isSubmitting={createMutation.isPending}
            error={mutationApiError(createMutation.error)}
          />
        </section>
      )}

      <MasterDetail list={listContent} />
    </div>
  );
}
```

- [ ] **Step 6: Convert the detail page into a right-pane panel**

In `web/src/app/glossary/[conceptId]/page.tsx`, remove the `Link` import and the full-page header (the `<header className="page-header">` block with the back link and `page-title`). Replace the import line:

```tsx
import { useParams, Link } from "react-router-dom";
```

with:

```tsx
import { useParams } from "react-router-dom";
```

Replace the entire `return (...)` block's outer wrapper and header. Change from:

```tsx
  return (
    <div className="page-concept-detail">
      <header className="page-header">
        <Link to="/glossary" className="back-link">
          &larr; Back to Glossary
        </Link>
        <h1 className="page-title">{concept.primaryTerm}</h1>
        <div className="concept-header-meta">
          <StatusBadge status={concept.status} />
          <span className="type-badge">{concept.termType}</span>
        </div>
      </header>
```

to:

```tsx
  return (
    <div className="concept-detail-panel">
      <header className="concept-panel-header">
        <h2 className="concept-panel-title">{concept.primaryTerm}</h2>
        <div className="concept-header-meta">
          <StatusBadge status={concept.status} />
          <span className="type-badge">{concept.termType}</span>
        </div>
      </header>
```

Leave the rest of the panel (Definition, Tags, Edit form, VariantList, RelationEditor) unchanged. The closing `</div>` of the wrapper stays.

- [ ] **Step 7: Nest the glossary routes in layout.tsx**

In `web/src/app/layout.tsx`, add the import:

```tsx
import EmptyState from "../components/shared/EmptyState";
```

Replace these two lines:

```tsx
          <Route path="glossary" element={<GlossaryPage />} />
          <Route path="glossary/:conceptId" element={<ConceptDetailPage />} />
```

with:

```tsx
          <Route path="glossary" element={<GlossaryPage />}>
            <Route
              index
              element={
                <EmptyState message="Select a term to view its definition." />
              }
            />
            <Route path=":conceptId" element={<ConceptDetailPage />} />
          </Route>
```

- [ ] **Step 8: Update the glossary integration tests**

In `web/tests/glossary.test.tsx`, the `ConceptDetailPage` describe block renders the panel in isolation. Two existing tests assume the old full-page header. Update them:

Replace the test `"shows back link to glossary list"` entirely with:

```tsx
  it("renders the term as a panel heading (no back link)", async () => {
    mockGetConcept.mockResolvedValue({ ...MOCK_CONCEPTS[0] });

    renderWithProviders(<ConceptDetailPage />, {
      route: "/glossary/c_1",
    });

    await waitFor(() => {
      expect(
        screen.getByRole("heading", { name: "스태미나" }),
      ).toBeInTheDocument();
    });
    expect(screen.queryByText(/back to glossary/i)).toBeNull();
  });
```

The other `ConceptDetailPage` tests still pass because they assert on the term text, Definition, Variants/Relations, Edit — all retained. Note: `ConceptDetailPage` rendered standalone (not inside a `<Route>`) still works because `useParams` reads from the `MemoryRouter` `initialEntries` path matched by the test helper's implicit route; if a test fails resolving params, wrap with `<Routes><Route path="/glossary/:conceptId" element={ui}/></Routes>` — but the existing tests already pass `route: "/glossary/c_1"` and read params successfully, so no wrapper change is needed.

- [ ] **Step 9: Run the glossary tests**

Run: `npx vitest run tests/glossary.test.tsx`
Expected: PASS (all ConceptTable, ConceptForm, VariantList, RelationEditor, GlossaryPage, ConceptDetailPage tests, including the new selected-row and panel-heading tests).

- [ ] **Step 10: Commit**

```bash
git add web/src/app/glossary web/src/components/glossary/ConceptTable.tsx web/src/app/layout.tsx web/tests/glossary.test.tsx
git commit -m "feat(web): glossary 3-pane master-detail with URL-driven selection"
```

---

### Task 3: Documents 3-pane (nested route, drop local state)

**Files:**
- Modify: `web/src/app/documents/page.tsx` (master container; remove `selectedId` state)
- Create: `web/src/app/documents/[documentId]/page.tsx` (right-pane panel) — replaces the inline detail logic
- Modify: `web/src/app/layout.tsx` (nest the documents routes)
- Test: `web/tests/review-documents.test.tsx` (update document expectations)

**Interfaces:**
- Consumes: `MasterDetail`, `documentQueries.detail(id)`, `documentQueries.list()`, `DocumentViewer`.
- Produces: `DocumentsPage` (default export) renders header + uploader + `<MasterDetail list={<documents table>} />`. `DocumentDetailPage` (default export) reads `:documentId` from `useParams`, fetches via `documentQueries.detail`, renders `DocumentViewer`.

- [ ] **Step 1: Write the detail panel**

```tsx
// web/src/app/documents/[documentId]/page.tsx
import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import DocumentViewer from "../../../components/documents/DocumentViewer";
import Loading from "../../../components/shared/Loading";
import ErrorState from "../../../components/shared/ErrorState";
import { documentQueries } from "../../../lib/queries";

export default function DocumentDetailPage() {
  const { documentId } = useParams<{ documentId: string }>();
  const detailQuery = useQuery({
    ...documentQueries.detail(documentId!),
    enabled: !!documentId,
  });

  if (detailQuery.isLoading) return <Loading label="Loading document..." />;
  if (detailQuery.isError || !detailQuery.data) {
    return (
      <ErrorState
        message={detailQuery.error?.message || "Failed to load document details"}
        onRetry={() => detailQuery.refetch()}
      />
    );
  }
  return <DocumentViewer document={detailQuery.data} />;
}
```

- [ ] **Step 2: Convert DocumentsPage into the master container**

Replace `web/src/app/documents/page.tsx` with:

```tsx
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import DocumentUploader from "../../components/documents/DocumentUploader";
import MasterDetail from "../../components/shared/MasterDetail";
import Loading from "../../components/shared/Loading";
import ErrorState from "../../components/shared/ErrorState";
import EmptyState from "../../components/shared/EmptyState";
import { documentQueries, useAnalyzeDocumentPath } from "../../lib/queries";
import { ApiError } from "../../lib/api";

export default function DocumentsPage() {
  const navigate = useNavigate();
  const { documentId } = useParams<{ documentId: string }>();

  const listQuery = useQuery(documentQueries.list());
  const analyzeMutation = useAnalyzeDocumentPath();

  function handleSelect(id: string) {
    navigate(`/documents/${id}`);
  }

  function extractError(err: unknown): string | null {
    if (err instanceof ApiError) {
      return err.body?.details || err.body?.message || null;
    }
    if (err instanceof Error) return err.message;
    return null;
  }

  const listContent = listQuery.isLoading ? (
    <Loading label="Loading documents..." />
  ) : listQuery.isError ? (
    <ErrorState
      message={listQuery.error.message || "Failed to load documents"}
      onRetry={() => listQuery.refetch()}
    />
  ) : listQuery.data?.length === 0 ? (
    <EmptyState message="No documents yet. Analyze a file path to get started." />
  ) : (
    <table className="data-table" aria-label="Documents">
      <thead>
        <tr>
          <th>Title</th>
          <th>Type</th>
          <th>Analyzed</th>
        </tr>
      </thead>
      <tbody>
        {listQuery.data?.map((doc) => (
          <tr
            key={doc.id}
            className={`data-row clickable ${
              documentId === doc.id ? "selected" : ""
            }`}
            onClick={() => handleSelect(doc.id)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                handleSelect(doc.id);
              }
            }}
            tabIndex={0}
            aria-label={`View ${doc.title}`}
          >
            <td className="term-cell">{doc.title}</td>
            <td>
              <span className="type-badge">{doc.mimeType.split("/")[1]}</span>
            </td>
            <td className="text-muted">
              {doc.analyzedAt
                ? new Date(doc.analyzedAt).toLocaleDateString()
                : "--"}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );

  return (
    <div className="page-documents">
      <header className="page-header">
        <h1 className="page-title">Documents</h1>
      </header>

      <section className="analyze-section" aria-label="Analyze document">
        <DocumentUploader
          onAnalyze={(path) =>
            analyzeMutation.mutateAsync(path).catch(() => {
              /* intentional: error surfaces via analyzeMutation.error */
            })
          }
          isAnalyzing={analyzeMutation.isPending}
          error={extractError(analyzeMutation.error)}
        />
      </section>

      <MasterDetail list={listContent} />
    </div>
  );
}
```

- [ ] **Step 3: Nest the documents routes in layout.tsx**

In `web/src/app/layout.tsx`, replace:

```tsx
          <Route path="documents" element={<DocumentsPage />} />
          <Route path="documents/:documentId" element={<DocumentDetailPage />} />
```

with:

```tsx
          <Route path="documents" element={<DocumentsPage />}>
            <Route
              index
              element={
                <EmptyState message="Select a document to view its contents." />
              }
            />
            <Route path=":documentId" element={<DocumentDetailPage />} />
          </Route>
```

(The `DocumentDetailPage` import already exists in layout.tsx; it now points at the new file at the same path.)

- [ ] **Step 4: Update document tests**

In `web/tests/review-documents.test.tsx`, find document-selection tests that render `DocumentsPage` and assert the detail appears after clicking a row. Because selection is now URL-driven, the detail panel is a separate route component. Update those tests to render the nested route tree. Replace any standalone `render(<DocumentsPage/>)` selection test with the route-tree form:

```tsx
import { MemoryRouter, Routes, Route } from "react-router-dom";
import DocumentsPage from "../src/app/documents/page";
import DocumentDetailPage from "../src/app/documents/[documentId]/page";
import EmptyState from "../src/components/shared/EmptyState";

function renderDocuments(client: QueryClient, route = "/documents") {
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path="/documents" element={<DocumentsPage />}>
            <Route index element={<EmptyState message="Select a document to view its contents." />} />
            <Route path=":documentId" element={<DocumentDetailPage />} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
```

For the "click selects a document" test: after clicking a row, assert the detail (e.g. the document title in the viewer) appears via `await screen.findByText(...)`. The click triggers navigation to `/documents/:id`, mounting `DocumentDetailPage`, which fetches via the mocked `apiClient.getDocument`. Ensure the document detail mock (`mockGetDocument` or equivalent already in this file) resolves the selected document.

- [ ] **Step 5: Run the documents/review tests**

Run: `npx vitest run tests/review-documents.test.tsx`
Expected: PASS. If a document selection test still references the removed inline `documents-layout` detail, fix it to use `renderDocuments` and `findByText` on the viewer content.

- [ ] **Step 6: Commit**

```bash
git add web/src/app/documents web/src/app/layout.tsx web/tests/review-documents.test.tsx
git commit -m "feat(web): documents 3-pane master-detail with URL-driven selection"
```

---

### Task 4: Review 3-pane (nested route, drop local state)

**Files:**
- Modify: `web/src/app/review/page.tsx` (master container; remove `selected` state, move actions into the panel)
- Create: `web/src/app/review/[issueId]/page.tsx` (right-pane panel with IssueDetail + ReviewActionPanel)
- Modify: `web/src/components/review/IssueList.tsx` (add `selectedId` highlight)
- Modify: `web/src/app/layout.tsx` (nest the review routes)
- Test: `web/tests/review-documents.test.tsx` (update review expectations)

**Interfaces:**
- Consumes: `MasterDetail`, `issueQueries.detail(id)`, `issueQueries.list()`, `IssueList`, `IssueDetail`, `ReviewActionPanel`, the issue mutation hooks, `createIssueActionRequest`.
- Produces: `ReviewPage` (default export) renders header + `<MasterDetail list={<IssueList .../>} />`. `IssueDetailPage` (default export) reads `:issueId` from `useParams`, fetches via `issueQueries.detail`, owns the action mutations. `IssueList` gains optional prop `selectedId?: string`.

- [ ] **Step 1: Add `selectedId` highlight to IssueList (failing test)**

Append a test to the review section of `web/tests/review-documents.test.tsx` (adjust mock issue shape to the existing `MOCK_ISSUES` constant in that file):

```tsx
  it("marks the selected issue row with the selected class", () => {
    const { container } = render(<IssueList issues={MOCK_ISSUES} selectedId={MOCK_ISSUES[0].id} />);
    const selected = container.querySelector(".data-row.selected");
    expect(selected).not.toBeNull();
  });
```

(Ensure `IssueList` is imported in the test file; it already is for existing review tests.)

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run tests/review-documents.test.tsx -t "marks the selected issue row"`
Expected: FAIL — no `.data-row.selected` element.

- [ ] **Step 3: Add `selectedId` to IssueList**

In `web/src/components/review/IssueList.tsx`, update the props and row className:

```tsx
interface Props {
  issues: readonly TermIssue[];
  onSelect?: (issue: TermIssue) => void;
  selectedId?: string;
}

export default function IssueList({ issues, onSelect, selectedId }: Props) {
```

Change the row className from:

```tsx
                className={`data-row ${onSelect ? "clickable" : ""}`}
```

to:

```tsx
                className={`data-row ${onSelect ? "clickable" : ""} ${
                  selectedId === issue.id ? "selected" : ""
                }`}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run tests/review-documents.test.tsx -t "marks the selected issue row"`
Expected: PASS.

- [ ] **Step 5: Write the issue detail panel**

```tsx
// web/src/app/review/[issueId]/page.tsx
import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import IssueDetail from "../../../components/review/IssueDetail";
import ReviewActionPanel from "../../../components/review/ReviewActionPanel";
import Loading from "../../../components/shared/Loading";
import ErrorState from "../../../components/shared/ErrorState";
import {
  issueQueries,
  useAcceptIssue,
  useDismissIssue,
  useResolveIssueAsNewConcept,
  useResolveIssueAsAlias,
  useResolveIssueAsForbidden,
} from "../../../lib/queries";
import { ApiError } from "../../../lib/api";
import {
  createIssueActionRequest,
  type ReviewActionKind,
} from "../../../lib/reviewActions";
import type {
  IssueActionPayload,
  IssueActionRequest,
} from "../../../lib/types";

type IssueActionMutate = (variables: {
  readonly id: string;
  readonly payload: IssueActionRequest;
}) => Promise<IssueActionPayload>;

export default function IssueDetailPage() {
  const { issueId } = useParams<{ issueId: string }>();
  const detailQuery = useQuery({
    ...issueQueries.detail(issueId!),
    enabled: !!issueId,
  });
  const selected = detailQuery.data ?? null;

  const acceptMutation = useAcceptIssue();
  const dismissMutation = useDismissIssue();
  const resolveNewConceptMutation = useResolveIssueAsNewConcept();
  const resolveAliasMutation = useResolveIssueAsAlias();
  const resolveForbiddenMutation = useResolveIssueAsForbidden();

  const isMutating =
    acceptMutation.isPending ||
    dismissMutation.isPending ||
    resolveNewConceptMutation.isPending ||
    resolveAliasMutation.isPending ||
    resolveForbiddenMutation.isPending;

  const activeError =
    acceptMutation.error ||
    dismissMutation.error ||
    resolveNewConceptMutation.error ||
    resolveAliasMutation.error ||
    resolveForbiddenMutation.error;

  function runAction(kind: ReviewActionKind, mutate: IssueActionMutate): void {
    if (!selected) return;
    const payload = createIssueActionRequest(selected, kind);
    /* Error surfaces via the active mutation's error; detail refetches on invalidate. */
    mutate({ id: selected.id, payload }).catch(() => {
      /* intentional: error surfaces via mutation.error */
    });
  }

  function mutationApiError(err: unknown): ApiError | null {
    return err instanceof ApiError ? err : null;
  }

  if (detailQuery.isLoading) return <Loading label="Loading issue..." />;
  if (detailQuery.isError || !selected) {
    return (
      <ErrorState
        message={detailQuery.error?.message || "Failed to load issue"}
        onRetry={() => detailQuery.refetch()}
      />
    );
  }

  return (
    <>
      <IssueDetail issue={selected} />
      <ReviewActionPanel
        issue={selected}
        onAccept={() => runAction("accept", acceptMutation.mutateAsync)}
        onDismiss={() => runAction("dismiss", dismissMutation.mutateAsync)}
        onResolveAsNewConcept={() =>
          runAction("new-concept", resolveNewConceptMutation.mutateAsync)
        }
        onResolveAsAlias={() =>
          runAction("alias", resolveAliasMutation.mutateAsync)
        }
        onResolveAsForbidden={() =>
          runAction("forbidden", resolveForbiddenMutation.mutateAsync)
        }
        isMutating={isMutating}
        error={mutationApiError(activeError)}
      />
    </>
  );
}
```

- [ ] **Step 6: Convert ReviewPage into the master container**

Replace `web/src/app/review/page.tsx` with:

```tsx
import { useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import type { TermIssue } from "../../lib/types";
import IssueList from "../../components/review/IssueList";
import MasterDetail from "../../components/shared/MasterDetail";
import Loading from "../../components/shared/Loading";
import ErrorState from "../../components/shared/ErrorState";
import { issueQueries } from "../../lib/queries";

export default function ReviewPage() {
  const navigate = useNavigate();
  const { issueId } = useParams<{ issueId: string }>();

  const listQuery = useQuery(issueQueries.list());

  function handleSelect(issue: TermIssue) {
    navigate(`/review/${issue.id}`);
  }

  const listContent = listQuery.isLoading ? (
    <Loading label="Loading issues..." />
  ) : listQuery.isError ? (
    <ErrorState
      message={listQuery.error.message || "Failed to load issues"}
      onRetry={() => listQuery.refetch()}
    />
  ) : (
    <IssueList
      issues={listQuery.data ?? []}
      onSelect={handleSelect}
      selectedId={issueId}
    />
  );

  return (
    <div className="page-review">
      <header className="page-header">
        <h1 className="page-title">Review Queue</h1>
      </header>

      <MasterDetail list={listContent} />
    </div>
  );
}
```

- [ ] **Step 7: Nest the review routes in layout.tsx**

In `web/src/app/layout.tsx`, add the import:

```tsx
import IssueDetailPage from "./review/[issueId]/page";
```

Replace:

```tsx
          <Route path="review" element={<ReviewPage />} />
```

with:

```tsx
          <Route path="review" element={<ReviewPage />}>
            <Route
              index
              element={
                <EmptyState message="Select an issue to review its details and actions." />
              }
            />
            <Route path=":issueId" element={<IssueDetailPage />} />
          </Route>
```

- [ ] **Step 8: Update review tests**

In `web/tests/review-documents.test.tsx`, update review selection tests to use the nested route tree (mirror the `renderDocuments` helper from Task 3, for review):

```tsx
import IssueDetailPage from "../src/app/review/[issueId]/page";

function renderReview(client: QueryClient, route = "/review") {
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>
        <Routes>
          <Route path="/review" element={<ReviewPage />}>
            <Route index element={<EmptyState message="Select an issue to review its details and actions." />} />
            <Route path=":issueId" element={<IssueDetailPage />} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
```

For the "select issue shows detail/actions" test: after clicking a row, the panel fetches via the mocked `apiClient.getIssue`. Add/confirm a `mockGetIssue` in the file's apiClient mock returning the selected issue, then assert the detail surface and action buttons appear via `await screen.findByText(...)`. For the empty placeholder test, render at `/review` and assert the placeholder text is present.

- [ ] **Step 9: Run the documents/review tests**

Run: `npx vitest run tests/review-documents.test.tsx`
Expected: PASS (document + review selection, highlight, and placeholder tests).

- [ ] **Step 10: Commit**

```bash
git add web/src/app/review web/src/components/review/IssueList.tsx web/src/app/layout.tsx web/tests/review-documents.test.tsx
git commit -m "feat(web): review 3-pane master-detail with URL-driven selection"
```

---

### Task 5: Detail-panel styling, graph visual unification, full verification

**Files:**
- Modify: `web/src/index.css` (add `.concept-detail-panel` / `.concept-panel-header` / `.concept-panel-title` styles; align graph detail panel)
- Modify: `web/src/app/graph/page.tsx` (wrap the node/edge detail in `.md-detail` for visual consistency — only if graph renders detail in a side region; otherwise skip)
- Test: full suite

**Interfaces:**
- Consumes: classes introduced in Tasks 1–4.
- Produces: no new public component API; CSS-only + optional graph class change.

- [ ] **Step 1: Add panel CSS**

Append to `web/src/index.css` (near the existing concept-detail styles):

```css
/* ── Concept detail panel (right pane) ── */

.concept-detail-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-lg);
}

.concept-panel-header {
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.concept-panel-title {
  font-size: 1.25rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--color-text);
}
```

- [ ] **Step 2: Inspect the graph page detail region**

Run: `grep -n "DetailPanel\|detail\|NodeDetail\|EdgeDetail\|className=" web/src/app/graph/page.tsx`
Decision: if the graph page already renders `NodeDetailPanel`/`EdgeDetailPanel` in a dedicated right region with its own class, leave behavior unchanged and (optionally) add `md-detail` to that region's className for visual parity. If the detail is an overlay/modal, skip — no change. Graph selection stays canvas-driven (no nested route). Record the decision in the commit message.

- [ ] **Step 3: Run the full test suite**

Run: `npx vitest run`
Expected: PASS for all files (master-detail, glossary, review-documents, shell, graph, error-empty-states, typecheck).

- [ ] **Step 4: Typecheck + build**

Run: `npx tsc --noEmit && npm run build`
Expected: no type errors; build succeeds. (`tests/typecheck.test.ts` also guards types within vitest.)

- [ ] **Step 5: Commit**

```bash
git add web/src/index.css web/src/app/graph/page.tsx
git commit -m "feat(web): unify detail-panel styling across master-detail tabs"
```

---

## Self-Review Notes

- **Spec coverage:** Glossary 3-pane (Task 2), apply to all tabs (Tasks 2–4 + Task 5 graph note), URL-driven selection (nested routes in Tasks 2–4), single consistent layout (`MasterDetail` Task 1), left rail kept (no removal; CSS unchanged for `.app-nav`), responsive `<1024px` (Task 1 media query), placeholder/error/empty handling (index routes + panel ErrorState in each task). All covered.
- **No new endpoints:** detail panels use existing `*.detail(id)` query factories.
- **Type consistency:** `selectedId?: string` added to `ConceptTable` and `IssueList`; `documentId`/`conceptId`/`issueId` param names match the route definitions; `IssueActionMutate` signature matches the original ReviewPage usage.
- **Naming:** detail components keep their existing default-export names (`ConceptDetailPage`, `DocumentDetailPage`, `IssueDetailPage`) so layout.tsx imports stay consistent.
