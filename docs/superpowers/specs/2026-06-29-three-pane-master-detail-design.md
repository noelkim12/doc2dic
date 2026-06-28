# 3-Pane Master-Detail Layout for Web Frontend

Date: 2026-06-29
Status: Approved (design)

## Problem

The web frontend (`web/`, React + react-router) has inconsistent list→detail
patterns across tabs, and none of them sync the selection to the URL.

- **Glossary**: clicking a term performs a full **page transition** to
  `/glossary/:conceptId` (visually 2-bay: nav + content). The list disappears.
- **Documents** / **Review**: already render an in-page 2-pane (list + detail)
  but driven by **local React state** (`selectedId` / `selected`), with no URL
  sync — refresh/back/forward loses the selection.

We want a unified **3-bay layout** (left nav rail + center master list + right
detail pane). Clicking a word keeps the list visible and shows its description
in the right pane, with the selection reflected in the URL.

## Goals

- Glossary: click a term → description/detail appears in a **right pane**; the
  list stays visible in the center (no full-page transition).
- Apply the same master-detail pattern across **all applicable tabs**
  (Glossary, Documents, Review).
- **URL-driven selection**: selecting an item updates the URL; refresh, back/
  forward, and bookmarking restore the selection.
- One consistent layout/CSS pattern instead of three ad-hoc ones.

## Non-Goals (YAGNI)

- Resizable / draggable pane splitters (no extra library).
- Converting Graph's canvas interaction to nested routes (it has no list).
- Home / Settings gaining a detail pane.

## Approach (chosen: A — nested routes + shared 3-pane shell)

Visual 3-bay = **app nav (shell column 1)** + **master list (main, left)** +
**detail (main, right)**. The app shell keeps its `nav | main` 2-column grid;
inside `main`, each list-detail tab renders a `list | detail(<Outlet/>)`
2-column grid. URL sync comes for free from react-router nested routes.

### Routing (`web/src/app/layout.tsx`)

```
/                       Home               (single pane)
/glossary               GlossaryPage       (list center + <Outlet/> right)
  index                 placeholder        ("Select a term to see its details")
  /glossary/:conceptId  ConceptDetailPanel (right detail)
/documents              DocumentsPage      (list + <Outlet/>)
  index                 placeholder
  /documents/:documentId DocumentDetailPanel
/review                 ReviewPage         (list + <Outlet/>)
  index                 placeholder
  /review/:issueId      IssueDetailPanel
/graph                  GraphPage          (canvas + right detail; visual-only unification)
/settings               SettingsPage       (single pane)
```

The current top-level `<Routes>` in `layout.tsx` becomes nested. Selection
handlers call `navigate('/glossary/:id')` instead of `setState`.

### Components

New
- `web/src/components/shared/MasterDetail.tsx` — 3-pane grid wrapper rendering a
  `list` slot (center) and `<Outlet/>` (right). Provides the shared
  `.master-detail / .md-list / .md-detail` structure.

Refactor
- `web/src/app/glossary/page.tsx` → master container: header + New Concept +
  ConceptForm + ConceptTable in the center, `<Outlet/>` on the right.
- `web/src/app/glossary/[conceptId]/page.tsx` → `ConceptDetailPanel`: drops the
  full-page header and "Back to Glossary" link (list stays visible); keeps
  Definition/Tags, Edit form, VariantList, RelationEditor. Reads `conceptId`
  from `useParams` and fetches via the existing `conceptQueries.detail`.
- `web/src/app/documents/page.tsx` → container + `documents/[documentId]/page.tsx`
  `DocumentDetailPanel`; remove local `selectedId`. Panel reads `documentId`
  from `useParams`, fetches via existing `getDocument(id)`.
- `web/src/app/review/page.tsx` → container + `review/[issueId]/page.tsx`
  `IssueDetailPanel`; remove local `selected`. Panel reads `issueId` from
  `useParams`, resolves the issue from the `issueQueries.list()` cache (no new
  endpoint); mutations invalidate the list as today.
- `ConceptTable`, `IssueList`, and the documents table → accept a `selectedId`
  (derived from `useParams`) for row highlight; `onSelect` navigates.

Index routes render an `EmptyState` placeholder in the right pane.

### CSS / left rail / responsive (`web/src/index.css`)

- Left rail: keep the existing nav, normalized to a fixed `220px` slim rail
  (labels kept — only 6 items, so no icon-only treatment).
- `.master-detail { display: grid; grid-template-columns: minmax(0,1fr)
  minmax(360px, 0.85fr); gap; height: 100%; }`; `.md-list` and `.md-detail`
  each `overflow: auto` for independent scrolling.
- Selected row highlight reuses the existing `.data-row.selected` style.
- Responsive: `≥1024px` full 3-bay; `<1024px` collapses to a single column with
  the detail stacked below the list. No JS-driven resizing.

## Data flow

1. User clicks a row → `onSelect(id)` → `navigate('/<tab>/<id>')`.
2. Nested `:id` route mounts the detail panel; `useParams` provides the id.
3. Panel fetches/derives the entity (existing queries / list cache).
4. Mutations (edit concept, add alias, issue actions) invalidate their queries
   as today; the URL/selection is unaffected.
5. Index route (no id) → right pane shows the placeholder EmptyState.

## Error / empty handling

- List load error/empty: unchanged (ErrorState / EmptyState in the center).
- Detail load error: ErrorState with retry in the right pane.
- No selection: placeholder EmptyState in the right pane.
- Invalid/stale id (e.g., deleted item): detail query/derivation yields nothing
  → right pane shows a "not found" ErrorState.

## Testing

- `web/tests/glossary.test.tsx`: clicking a term renders the detail in the right
  pane and updates the URL to `/glossary/:id` (was: navigates to a separate
  page); add index-placeholder and back-navigation cases.
- `web/tests/review-documents.test.tsx`: selection drives the URL and detail
  pane; remove assumptions about local-state-only selection.
- `web/tests/shell.test.tsx`: reflect the nested route structure.
- Reuse `MemoryRouter` with initial entries for URL-restore cases.

## Risks

- Moderate refactor of Documents/Review from local state to nested routes; their
  existing detail components already take the entity, so the panels become thin
  `useParams` + lookup wrappers.
- Test updates needed wherever selection was asserted via local state.
