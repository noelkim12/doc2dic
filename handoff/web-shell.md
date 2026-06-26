# Task: T10 Web Shell / API Client / Query Helpers

## Scope
Allowed paths: `web/src/lib/`, `web/src/app/layout.tsx`, `web/src/app/page.tsx`, `web/src/main.tsx`, `web/src/components/shared/`, `web/tests/`, `web/vitest.config.ts`, `web/index.css`
No frozen paths edited. No orchestrator approval needed.

## Files Changed
- `web/src/lib/api.ts` (created) - API client with typed errors
- `web/src/lib/query.tsx` (created) - TanStack Query provider
- `web/src/lib/queries.ts` (created) - queryOptions helpers
- `web/src/index.css` (created) - shell design system CSS
- `web/src/main.tsx` (modified) - uses extracted QueryProvider + CSS import
- `web/src/components/shared/StatusBadge.tsx` (modified) - handles IssueStatus too
- `web/tests/shell.test.tsx` (created) - 20 smoke tests
- `web/tests/setup.ts` (created) - vitest jest-dom setup
- `web/vitest.config.ts` (created) - jsdom config

## Commands Run
1. `npm --prefix web run typecheck` -> exit 0 (clean)
2. `npm --prefix web run test -- --run tests/shell.test.tsx` -> 20/20 pass
3. `npm --prefix web install -D @testing-library/react @testing-library/jest-dom jsdom` -> 58 packages, 0 vulns

## Evidence Path
`.omo/evidence/task-10-parallel-implementation.md`

## Risks
None

## Follow-up
Feature pages (T21-T23, T25) should use `lib/api`, `lib/queries`, `lib/query`. HomePage is still a stub.
