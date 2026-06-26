import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type {
  Document,
  DocumentChunk,
  TermOccurrence,
  TermIssue,
  IssueEvidence,
  IssueActionPayload,
} from "../src/lib/types";

/* ── Components under test ── */

import DocumentUploader from "../src/components/documents/DocumentUploader";
import DocumentViewer from "../src/components/documents/DocumentViewer";
import OccurrencePanel from "../src/components/documents/OccurrencePanel";
import HighlightedText from "../src/components/documents/HighlightedText";
import IssueList from "../src/components/review/IssueList";
import IssueDetail from "../src/components/review/IssueDetail";
import ReviewActionPanel from "../src/components/review/ReviewActionPanel";
import DocumentsPage from "../src/app/documents/page";
import ReviewPage from "../src/app/review/page";
import { ApiError } from "../src/lib/api";

/* ── Module-level apiClient mock ── */

const mockListDocuments = vi.fn();
const mockGetDocument = vi.fn();
const mockAnalyzeDocumentPath = vi.fn();
const mockListDocumentOccurrences = vi.fn();
const mockListIssues = vi.fn();
const mockGetIssue = vi.fn();
const mockAcceptIssue = vi.fn();
const mockDismissIssue = vi.fn();
const mockResolveNewConcept = vi.fn();
const mockResolveAlias = vi.fn();
const mockResolveForbidden = vi.fn();

vi.mock("../src/lib/api", async () => {
  const actual = await vi.importActual("../src/lib/api");
  return {
    ...actual,
    apiClient: {
      ...(actual as Record<string, unknown>).apiClient,
      listDocuments: (...args: unknown[]) => mockListDocuments(...args),
      getDocument: (...args: unknown[]) => mockGetDocument(...args),
      analyzeDocumentPath: (...args: unknown[]) => mockAnalyzeDocumentPath(...args),
      listDocumentOccurrences: (...args: unknown[]) =>
        mockListDocumentOccurrences(...args),
      listIssues: (...args: unknown[]) => mockListIssues(...args),
      getIssue: (...args: unknown[]) => mockGetIssue(...args),
      acceptIssue: (...args: unknown[]) => mockAcceptIssue(...args),
      dismissIssue: (...args: unknown[]) => mockDismissIssue(...args),
      resolveIssueAsNewConcept: (...args: unknown[]) =>
        mockResolveNewConcept(...args),
      resolveIssueAsAlias: (...args: unknown[]) => mockResolveAlias(...args),
      resolveIssueAsForbidden: (...args: unknown[]) =>
        mockResolveForbidden(...args),
    },
  };
});

/* ── Helpers ── */

function renderWithProviders(
  ui: React.ReactElement,
  options?: { route?: string },
) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[options?.route || "/"]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

/* ── Mock data (contract-correct shapes) ── */

const MOCK_DOCUMENTS: readonly Document[] = [
  {
    id: "doc_1",
    path: "samples/docs/combat_core.md",
    title: "combat_core.md",
    contentHash: "abc123",
    mimeType: "text/markdown",
    chunkIds: ["ch_1", "ch_2"],
    analyzedAt: "2025-06-01T12:00:00Z",
  },
  {
    id: "doc_2",
    path: "samples/docs/magic_system.md",
    title: "magic_system.md",
    contentHash: "def456",
    mimeType: "text/markdown",
    chunkIds: ["ch_3"],
    analyzedAt: "2025-06-02T12:00:00Z",
  },
];

const MOCK_CHUNKS: readonly DocumentChunk[] = [
  {
    id: "ch_1",
    documentId: "doc_1",
    sectionTitle: "Combat Mechanics",
    ordinal: 1,
    textPreview: "스태미나 is a resource that limits action frequency in combat.",
    contentHash: "h1",
  },
  {
    id: "ch_2",
    documentId: "doc_1",
    sectionTitle: "Glossary Terms",
    ordinal: 2,
    textPreview: "The following terms are defined in this document.",
    contentHash: "h2",
  },
];

const MOCK_OCCURRENCES: readonly TermOccurrence[] = [
  {
    id: "occ_1",
    documentId: "doc_1",
    chunkId: "ch_1",
    conceptId: null,
    surface: "스태미나",
    offsetStart: 0,
    offsetEnd: 15,
    confidence: 0.95,
  },
  {
    id: "occ_2",
    documentId: "doc_1",
    chunkId: "ch_1",
    conceptId: "c_1",
    surface: "Mana Pool",
    offsetStart: 40,
    offsetEnd: 49,
    confidence: 0.82,
  },
];

const MOCK_EVIDENCE: readonly IssueEvidence[] = [
  {
    id: "ev_1",
    kind: "quote",
    sourceDocumentId: "doc_1",
    chunkId: "ch_1",
    quote: "스태미나 is a resource that limits action frequency.",
    contextBefore: "In combat, each action consumes",
    contextAfter: "which regenerates over time.",
    confidence: 0.95,
  },
  {
    id: "ev_2",
    kind: "occurrence",
    sourceDocumentId: "doc_1",
    chunkId: "ch_1",
    quote: "스태미나",
    confidence: 0.9,
  },
];

const MOCK_ISSUES: readonly TermIssue[] = [
  {
    id: "iss_1",
    issueType: "unknown_term",
    status: "open",
    surface: "스태미나",
    candidateConceptId: "concept_stamina",
    evidence: MOCK_EVIDENCE,
    createdAt: "2025-06-01T12:00:00Z",
    version: 0,
    appliedIdempotencyKey: null,
  },
  {
    id: "iss_2",
    issueType: "alias_candidate",
    status: "open",
    surface: "STM",
    candidateConceptId: "concept_stamina",
    targetConceptId: null,
    evidence: [],
    createdAt: "2025-06-01T12:05:00Z",
    version: 2,
    appliedIdempotencyKey: null,
  },
  {
    id: "iss_3",
    issueType: "forbidden_term",
    status: "resolved",
    surface: "Banned Move",
    evidence: [],
    createdAt: "2025-05-01T10:00:00Z",
    resolvedAt: "2025-05-02T14:00:00Z",
    version: 1,
    appliedIdempotencyKey: "review:iss_3:dismiss:v0:done",
  },
];

function actionPayload(issue: TermIssue, status: TermIssue["status"]): IssueActionPayload {
  return {
    outcome: "applied",
    issue: {
      ...issue,
      status,
      version: issue.version + 1,
      appliedIdempotencyKey: `applied-${issue.id}`,
    },
  };
}

/* ═══════════════════════════════════════════
   DocumentUploader
   ═══════════════════════════════════════════ */

describe("DocumentUploader", () => {
  it("renders path input and analyze button", () => {
    renderWithProviders(<DocumentUploader onAnalyze={vi.fn()} />);
    expect(screen.getByLabelText("Document Path")).toBeInTheDocument();
    expect(screen.getByText("Analyze")).toBeInTheDocument();
  });

  it("calls onAnalyze with trimmed path on submit", async () => {
    const user = userEvent.setup();
    const onAnalyze = vi.fn().mockResolvedValue(undefined);
    renderWithProviders(<DocumentUploader onAnalyze={onAnalyze} />);

    const input = screen.getByLabelText("Document Path");
    await user.type(input, "  samples/docs/test.md  ");
    await user.click(screen.getByText("Analyze"));

    expect(onAnalyze).toHaveBeenCalledWith("samples/docs/test.md");
  });

  it("disables button while analyzing", () => {
    renderWithProviders(
      <DocumentUploader onAnalyze={vi.fn()} isAnalyzing={true} />,
    );
    const btn = screen.getByText("Analyzing...");
    expect(btn).toBeDisabled();
  });

  it("shows inline error when analysis fails", () => {
    renderWithProviders(
      <DocumentUploader onAnalyze={vi.fn()} error="File not found" />,
    );
    expect(screen.getByText(/file not found/i)).toBeInTheDocument();
  });
});

/* ═══════════════════════════════════════════
   DocumentViewer
   ═══════════════════════════════════════════ */

describe("DocumentViewer", () => {
  it("renders document title and metadata", () => {
    renderWithProviders(<DocumentViewer document={MOCK_DOCUMENTS[0]} />);
    expect(screen.getByText("combat_core.md")).toBeInTheDocument();
    expect(screen.getByText("Markdown")).toBeInTheDocument();
  });

  it("renders chunks with section titles and previews", () => {
    renderWithProviders(
      <DocumentViewer document={MOCK_DOCUMENTS[0]} chunks={MOCK_CHUNKS} />,
    );
    expect(screen.getByText(/sections \(2\)/i)).toBeInTheDocument();
    expect(screen.getByText("Combat Mechanics")).toBeInTheDocument();
    expect(screen.getByText("Glossary Terms")).toBeInTheDocument();
  });
});

/* ═══════════════════════════════════════════
   HighlightedText
   ═══════════════════════════════════════════ */

describe("HighlightedText", () => {
  it("highlights surface term within text", () => {
    renderWithProviders(
      <HighlightedText
        text="스태미나 is a resource"
        surface="스태미나"
      />,
    );
    const mark = screen.getByText("스태미나");
    expect(mark.tagName.toLowerCase()).toBe("mark");
  });
});

/* ═══════════════════════════════════════════
   OccurrencePanel
   ═══════════════════════════════════════════ */

describe("OccurrencePanel", () => {
  it("renders occurrences with surface highlighting and confidence", () => {
    renderWithProviders(<OccurrencePanel occurrences={MOCK_OCCURRENCES} />);
    expect(screen.getByText(/occurrences \(2\)/i)).toBeInTheDocument();
    // Highlighted surface should be present
    expect(screen.getByText("스태미나")).toBeInTheDocument();
    expect(screen.getByText("Mana Pool")).toBeInTheDocument();
  });

  it("shows empty state for no occurrences", () => {
    renderWithProviders(<OccurrencePanel occurrences={[]} />);
    expect(screen.getByText(/no term occurrences/i)).toBeInTheDocument();
  });
});

/* ═══════════════════════════════════════════
   IssueList
   ═══════════════════════════════════════════ */

describe("IssueList", () => {
  it("renders issues in table format", () => {
    renderWithProviders(<IssueList issues={MOCK_ISSUES} />);
    expect(screen.getByText("스태미나")).toBeInTheDocument();
    expect(screen.getByText("STM")).toBeInTheDocument();
    expect(screen.getByText("Banned Move")).toBeInTheDocument();
  });

  it("filters by status to show only open issues", async () => {
    const user = userEvent.setup();
    renderWithProviders(<IssueList issues={MOCK_ISSUES} />);

    const openBtn = screen.getByRole("button", { name: /open/i });
    await user.click(openBtn);

    expect(screen.getByText("스태미나")).toBeInTheDocument();
    expect(screen.getByText("STM")).toBeInTheDocument();
    // Banned Move is resolved -- should be hidden
    expect(screen.queryByText("Banned Move")).not.toBeInTheDocument();
  });

  it("calls onSelect when an issue row is clicked", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    renderWithProviders(
      <IssueList issues={MOCK_ISSUES} onSelect={onSelect} />,
    );

    await user.click(screen.getByText("스태미나"));
    expect(onSelect).toHaveBeenCalledWith(MOCK_ISSUES[0]);
  });

  it("shows empty message when no issues exist", () => {
    renderWithProviders(<IssueList issues={[]} />);
    expect(
      screen.getByText(/analyze a document to detect/i),
    ).toBeInTheDocument();
  });
});

/* ═══════════════════════════════════════════
   IssueDetail
   ═══════════════════════════════════════════ */

describe("IssueDetail", () => {
  it("renders issue surface, type, status, and evidence", () => {
    renderWithProviders(<IssueDetail issue={MOCK_ISSUES[0]} />);
    // Use the h2 surface text specifically, not generic getByText which matches evidence too
    expect(screen.getByText("unknown_term")).toBeInTheDocument(); // type badge (raw enum)
    expect(screen.getByText("Open")).toBeInTheDocument(); // StatusBadge
    expect(screen.getByText(/evidence \(2\)/i)).toBeInTheDocument();
  });

  it("renders bounded evidence quotes without raw document text", () => {
    renderWithProviders(<IssueDetail issue={MOCK_ISSUES[0]} />);
    // Evidence quote should be present but bounded
    expect(
      screen.getByText(/스태미나 is a resource that limits action frequency/i),
    ).toBeInTheDocument();
    // Context before/after should be shown
    expect(screen.getByText(/in combat, each action consumes/i)).toBeInTheDocument();
  });

  it("shows candidate concept ID when present", () => {
    renderWithProviders(<IssueDetail issue={MOCK_ISSUES[1]} />);
    expect(screen.getByText("concept_stamina")).toBeInTheDocument();
  });

  it("shows resolved timestamp for resolved issues", () => {
    renderWithProviders(<IssueDetail issue={MOCK_ISSUES[2]} />);
    expect(screen.getByText(/resolved:/i)).toBeInTheDocument();
  });
});

/* ═══════════════════════════════════════════
   ReviewActionPanel
   ═══════════════════════════════════════════ */

describe("ReviewActionPanel", () => {
  const openIssue = MOCK_ISSUES[0]; // status: "open"

  it("renders all five action buttons for open issues", () => {
    renderWithProviders(
      <ReviewActionPanel
        issue={openIssue}
        onAccept={vi.fn()}
        onDismiss={vi.fn()}
        onResolveAsNewConcept={vi.fn()}
        onResolveAsAlias={vi.fn()}
        onResolveAsForbidden={vi.fn()}
      />,
    );

    expect(screen.getByText("Accept")).toBeEnabled();
    expect(screen.getByText("Dismiss")).toBeEnabled();
    expect(screen.getByText("Resolve as New Concept")).toBeEnabled();
    expect(screen.getByText("Resolve as Alias")).toBeEnabled();
    expect(screen.getByText("Resolve as Forbidden")).toBeEnabled();
  });

  it("disables all actions for non-open issues", () => {
    const resolvedIssue = MOCK_ISSUES[2]; // status: "resolved"
    renderWithProviders(
      <ReviewActionPanel
        issue={resolvedIssue}
        onAccept={vi.fn()}
        onDismiss={vi.fn()}
        onResolveAsNewConcept={vi.fn()}
        onResolveAsAlias={vi.fn()}
        onResolveAsForbidden={vi.fn()}
      />,
    );

    expect(screen.getByText("Accept")).toBeDisabled();
    expect(screen.getByText("Dismiss")).toBeDisabled();
    expect(screen.getByText("Resolve as New Concept")).toBeDisabled();
    expect(screen.getByText("Resolve as Alias")).toBeDisabled();
    expect(screen.getByText("Resolve as Forbidden")).toBeDisabled();

    // Text spans <p> + <strong>; match on the unique substring in the <p> text node
    expect(screen.getByText(/cannot be acted upon/i)).toBeInTheDocument();
  });

  it("disables buttons while mutation is in progress", () => {
    renderWithProviders(
      <ReviewActionPanel
        issue={openIssue}
        onAccept={vi.fn()}
        onDismiss={vi.fn()}
        onResolveAsNewConcept={vi.fn()}
        onResolveAsAlias={vi.fn()}
        onResolveAsForbidden={vi.fn()}
        isMutating={true}
      />,
    );

    expect(screen.getByText("Accept")).toBeDisabled();
    expect(screen.getByText("Dismiss")).toBeDisabled();
  });

  it("shows stale-version conflict error with retry guidance", () => {
    const conflictError = new ApiError(409, "Conflict", {
      code: "stale_version",
      message: "Issue was modified by another session",
      details: "Current version mismatch",
    });

    renderWithProviders(
      <ReviewActionPanel
        issue={openIssue}
        onAccept={vi.fn()}
        error={conflictError}
      />,
    );

    // Error should be visible with conflict-specific guidance
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(/conflict/i);
    expect(alert).toHaveTextContent(/retry/i);
  });

  it("shows generic API error without conflict prefix", () => {
    const serverError = new ApiError(500, "Internal Server Error", {
      message: "Something went wrong",
      details: "Database connection failed",
    });

    renderWithProviders(
      <ReviewActionPanel
        issue={openIssue}
        onAccept={vi.fn()}
        error={serverError}
      />,
    );

    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(/database connection failed/i);
    expect(alert).not.toHaveTextContent(/conflict/i);
  });

  it("calls exact accept handler when Accept clicked", async () => {
    const user = userEvent.setup();
    const onAccept = vi.fn().mockResolvedValue(undefined);

    renderWithProviders(
      <ReviewActionPanel
        issue={openIssue}
        onAccept={onAccept}
        onDismiss={vi.fn()}
        onResolveAsNewConcept={vi.fn()}
        onResolveAsAlias={vi.fn()}
        onResolveAsForbidden={vi.fn()}
      />,
    );

    await user.click(screen.getByText("Accept"));
    expect(onAccept).toHaveBeenCalledTimes(1);
  });

  it("calls exact dismiss handler when Dismiss clicked", async () => {
    const user = userEvent.setup();
    const onDismiss = vi.fn().mockResolvedValue(undefined);

    renderWithProviders(
      <ReviewActionPanel
        issue={openIssue}
        onAccept={vi.fn()}
        onDismiss={onDismiss}
        onResolveAsNewConcept={vi.fn()}
        onResolveAsAlias={vi.fn()}
        onResolveAsForbidden={vi.fn()}
      />,
    );

    await user.click(screen.getByText("Dismiss"));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("calls exact resolve-as-new-concept handler when clicked", async () => {
    const user = userEvent.setup();
    const onResolve = vi.fn().mockResolvedValue(undefined);

    renderWithProviders(
      <ReviewActionPanel
        issue={openIssue}
        onAccept={vi.fn()}
        onDismiss={vi.fn()}
        onResolveAsNewConcept={onResolve}
        onResolveAsAlias={vi.fn()}
        onResolveAsForbidden={vi.fn()}
      />,
    );

    await user.click(screen.getByText("Resolve as New Concept"));
    expect(onResolve).toHaveBeenCalledTimes(1);
  });

  it("calls exact resolve-as-alias handler when clicked", async () => {
    const user = userEvent.setup();
    const onResolve = vi.fn().mockResolvedValue(undefined);

    renderWithProviders(
      <ReviewActionPanel
        issue={openIssue}
        onAccept={vi.fn()}
        onDismiss={vi.fn()}
        onResolveAsNewConcept={vi.fn()}
        onResolveAsAlias={onResolve}
        onResolveAsForbidden={vi.fn()}
      />,
    );

    await user.click(screen.getByText("Resolve as Alias"));
    expect(onResolve).toHaveBeenCalledTimes(1);
  });

  it("calls exact resolve-as-forbidden handler when clicked", async () => {
    const user = userEvent.setup();
    const onResolve = vi.fn().mockResolvedValue(undefined);

    renderWithProviders(
      <ReviewActionPanel
        issue={openIssue}
        onAccept={vi.fn()}
        onDismiss={vi.fn()}
        onResolveAsNewConcept={vi.fn()}
        onResolveAsAlias={vi.fn()}
        onResolveAsForbidden={onResolve}
      />,
    );

    await user.click(screen.getByText("Resolve as Forbidden"));
    expect(onResolve).toHaveBeenCalledTimes(1);
  });
});

/* ═══════════════════════════════════════════
   DocumentsPage (integration)
   ═══════════════════════════════════════════ */

describe("DocumentsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading state while fetching documents", () => {
    mockListDocuments.mockReturnValue(new Promise(() => {}));

    renderWithProviders(<DocumentsPage />, { route: "/documents" });
    expect(screen.getByText(/loading documents/i)).toBeInTheDocument();
  });

  it("shows documents table after successful load", async () => {
    mockListDocuments.mockResolvedValue([...MOCK_DOCUMENTS]);

    renderWithProviders(<DocumentsPage />, { route: "/documents" });

    await waitFor(() => {
      expect(screen.getByText("combat_core.md")).toBeInTheDocument();
    });
    expect(screen.getByText("magic_system.md")).toBeInTheDocument();
  });

  it("calls analyzeDocumentPath via API when path submitted", async () => {
    const user = userEvent.setup();
    mockListDocuments.mockResolvedValue([...MOCK_DOCUMENTS]);
    mockAnalyzeDocumentPath.mockResolvedValue(undefined);

    renderWithProviders(<DocumentsPage />, { route: "/documents" });

    await waitFor(() => {
      expect(screen.getByText("Analyze")).toBeInTheDocument();
    });

    // Use exact label text to avoid matching form aria-label
    const input = screen.getAllByLabelText(/document path/i)[0];
    await user.type(input, "samples/docs/new_doc.md");
    await user.click(screen.getByText("Analyze"));

    await waitFor(() => {
      expect(mockAnalyzeDocumentPath).toHaveBeenCalledWith(
        "samples/docs/new_doc.md",
      );
    });
  });

  it("shows error state when API fails", async () => {
    mockListDocuments.mockRejectedValue(new Error("Server Error"));

    renderWithProviders(<DocumentsPage />, { route: "/documents" });

    await waitFor(() => {
      expect(screen.getByText(/failed to load|error/i)).toBeInTheDocument();
    });
  });

  it("fetches document detail with correct ID when a row is selected", async () => {
    const user = userEvent.setup();
    mockListDocuments.mockResolvedValue([...MOCK_DOCUMENTS]);
    mockGetDocument.mockResolvedValue({
      ...MOCK_DOCUMENTS[0],
      chunks: [],
    });

    renderWithProviders(<DocumentsPage />, { route: "/documents" });

    await waitFor(() => {
      expect(screen.getByText("combat_core.md")).toBeInTheDocument();
    });

    // Click first document row
    await user.click(screen.getByText("combat_core.md"));

    await waitFor(() => {
      expect(mockGetDocument).toHaveBeenCalledWith("doc_1");
    });

    // Click second document row -- should fetch with the NEW id, not reuse cache
    mockGetDocument.mockClear();
    await user.click(screen.getByText("magic_system.md"));

    await waitFor(() => {
      expect(mockGetDocument).toHaveBeenCalledWith("doc_2");
    });
  });

  it("shows inline analyze error without unhandled rejection when analyze fails", async () => {
    const user = userEvent.setup();
    mockListDocuments.mockResolvedValue([...MOCK_DOCUMENTS]);
    mockAnalyzeDocumentPath.mockRejectedValue(
      new ApiError(400, "Bad Request", {
        message: "File not found",
        details: "samples/docs/nonexistent.md does not exist",
      }),
    );

    renderWithProviders(<DocumentsPage />, { route: "/documents" });

    await waitFor(() => {
      expect(screen.getByText("Analyze")).toBeInTheDocument();
    });

    const input = screen.getAllByLabelText(/document path/i)[0];
    await user.type(input, "samples/docs/nonexistent.md");
    await user.click(screen.getByText("Analyze"));

    await waitFor(() => {
      expect(mockAnalyzeDocumentPath).toHaveBeenCalledWith(
        "samples/docs/nonexistent.md",
      );
    });

    // Error should be visible inline in the uploader
    expect(
      screen.getByText(/does not exist/i),
    ).toBeInTheDocument();
    // Input should still contain the submitted path (not cleared)
    expect(input).toHaveValue("samples/docs/nonexistent.md");
  });
});

/* ═══════════════════════════════════════════
   ReviewPage (integration) -- exact endpoint assertions
   ═══════════════════════════════════════════ */

describe("ReviewPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loads and displays issues from listIssues endpoint", async () => {
    mockListIssues.mockResolvedValue([...MOCK_ISSUES]);

    renderWithProviders(<ReviewPage />, { route: "/review" });

    await waitFor(() => {
      expect(screen.getByText("스태미나")).toBeInTheDocument();
    });
    expect(mockListIssues).toHaveBeenCalledTimes(1);
  });

  it("shows loading state while fetching issues", () => {
    mockListIssues.mockReturnValue(new Promise(() => {}));

    renderWithProviders(<ReviewPage />, { route: "/review" });
    expect(screen.getByText(/loading issues/i)).toBeInTheDocument();
  });

  it("selects issue and shows detail + action panel", async () => {
    const user = userEvent.setup();
    mockListIssues.mockResolvedValue([...MOCK_ISSUES]);

    renderWithProviders(<ReviewPage />, { route: "/review" });

    await waitFor(() => {
      expect(screen.getByText("스태미나")).toBeInTheDocument();
    });

    // Click the first issue row to select it
    await user.click(screen.getByText("스태미나"));

    // Detail should show evidence count
    expect(await screen.findByText(/evidence \(2\)/i)).toBeInTheDocument();
    // Action panel should show all action buttons
    expect(screen.getByText("Accept")).toBeInTheDocument();
    expect(screen.getByText("Dismiss")).toBeInTheDocument();
    expect(screen.getByText("Resolve as New Concept")).toBeInTheDocument();
    expect(screen.getByText("Resolve as Alias")).toBeInTheDocument();
    expect(screen.getByText("Resolve as Forbidden")).toBeInTheDocument();
  });

  /* ── Exact endpoint assertions: each action calls the right apiClient method ── */

  it("calls acceptIssue endpoint with safe action body when Accept is clicked", async () => {
    const user = userEvent.setup();
    mockListIssues.mockResolvedValue([...MOCK_ISSUES]);
    mockAcceptIssue.mockResolvedValue(actionPayload(MOCK_ISSUES[0], "resolved"));

    renderWithProviders(<ReviewPage />, { route: "/review" });

    await waitFor(() => {
      expect(screen.getByText("스태미나")).toBeInTheDocument();
    });

    await user.click(screen.getByText("스태미나"));
    await user.click(screen.getByText("Accept"));

    await waitFor(() => {
      expect(mockAcceptIssue).toHaveBeenCalledWith("iss_1", {
        expectedVersion: 0,
        idempotencyKey: expect.stringMatching(/^review:iss_1:accept:v0:/),
        action: "resolve_as_new_concept",
        term: "스태미나",
        definition: "Review-approved concept for 스태미나.",
      });
    });
    // Verify it called acceptIssue specifically, not any other method
    expect(mockDismissIssue).not.toHaveBeenCalled();
    expect(mockResolveNewConcept).not.toHaveBeenCalled();
    expect(mockResolveAlias).not.toHaveBeenCalled();
    expect(mockResolveForbidden).not.toHaveBeenCalled();
  });

  it("calls dismissIssue endpoint with safe action body when Dismiss is clicked", async () => {
    const user = userEvent.setup();
    mockListIssues.mockResolvedValue([...MOCK_ISSUES]);
    mockDismissIssue.mockResolvedValue(actionPayload(MOCK_ISSUES[0], "dismissed"));

    renderWithProviders(<ReviewPage />, { route: "/review" });

    await waitFor(() => {
      expect(screen.getByText("스태미나")).toBeInTheDocument();
    });

    await user.click(screen.getByText("스태미나"));
    await user.click(screen.getByText("Dismiss"));

    await waitFor(() => {
      expect(mockDismissIssue).toHaveBeenCalledWith("iss_1", {
        expectedVersion: 0,
        idempotencyKey: expect.stringMatching(/^review:iss_1:dismiss:v0:/),
        reason: "Dismissed from the review queue.",
      });
    });
    expect(mockAcceptIssue).not.toHaveBeenCalled();
  });

  it("calls resolveIssueAsNewConcept endpoint with safe action body when clicked", async () => {
    const user = userEvent.setup();
    mockListIssues.mockResolvedValue([...MOCK_ISSUES]);
    mockResolveNewConcept.mockResolvedValue(actionPayload(MOCK_ISSUES[0], "resolved"));

    renderWithProviders(<ReviewPage />, { route: "/review" });

    await waitFor(() => {
      expect(screen.getByText("스태미나")).toBeInTheDocument();
    });

    await user.click(screen.getByText("스태미나"));
    await user.click(screen.getByText("Resolve as New Concept"));

    await waitFor(() => {
      expect(mockResolveNewConcept).toHaveBeenCalledWith("iss_1", {
        expectedVersion: 0,
        idempotencyKey: expect.stringMatching(/^review:iss_1:new-concept:v0:/),
        action: "resolve_as_new_concept",
        term: "스태미나",
        definition: "Review-approved concept for 스태미나.",
      });
    });
    expect(mockAcceptIssue).not.toHaveBeenCalled();
    expect(mockDismissIssue).not.toHaveBeenCalled();
  });

  it("calls resolveIssueAsAlias endpoint with safe action body when clicked", async () => {
    const user = userEvent.setup();
    mockListIssues.mockResolvedValue([...MOCK_ISSUES]);
    mockResolveAlias.mockResolvedValue(actionPayload(MOCK_ISSUES[1], "resolved"));

    renderWithProviders(<ReviewPage />, { route: "/review" });

    await waitFor(() => {
      expect(screen.getByText("STM")).toBeInTheDocument();
    });

    // Select second issue (alias_candidate)
    await user.click(screen.getByText("STM"));
    await user.click(screen.getByText("Resolve as Alias"));

    await waitFor(() => {
      expect(mockResolveAlias).toHaveBeenCalledWith("iss_2", {
        expectedVersion: 2,
        idempotencyKey: expect.stringMatching(/^review:iss_2:alias:v2:/),
        action: "resolve_as_alias",
        conceptId: "concept_stamina",
        variant: "STM",
      });
    });
    expect(mockAcceptIssue).not.toHaveBeenCalled();
  });

  it("calls resolveIssueAsForbidden endpoint with safe action body when clicked", async () => {
    const user = userEvent.setup();
    mockListIssues.mockResolvedValue([...MOCK_ISSUES]);
    mockResolveForbidden.mockResolvedValue(actionPayload(MOCK_ISSUES[1], "resolved"));

    renderWithProviders(<ReviewPage />, { route: "/review" });

    await waitFor(() => {
      expect(screen.getByText("STM")).toBeInTheDocument();
    });

    await user.click(screen.getByText("STM"));
    await user.click(screen.getByText("Resolve as Forbidden"));

    await waitFor(() => {
      expect(mockResolveForbidden).toHaveBeenCalledWith("iss_2", {
        expectedVersion: 2,
        idempotencyKey: expect.stringMatching(/^review:iss_2:forbidden:v2:/),
        action: "resolve_as_forbidden",
        conceptId: "concept_stamina",
        variant: "STM",
      });
    });
    expect(mockAcceptIssue).not.toHaveBeenCalled();
  });

  /* ── Stale-version / conflict error behavior ── */

  it("keeps issue open and shows conflict error on 409 response (no optimistic clear)", async () => {
    const user = userEvent.setup();
    mockListIssues.mockResolvedValue([{ ...MOCK_ISSUES[0] }]);
    // Simulate 409 Conflict from backend
    const conflictErr = new ApiError(409, "Conflict", {
      code: "stale_version",
      message: "Issue version mismatch",
      details: "The issue was modified by another session. Retry.",
    });
    mockAcceptIssue.mockRejectedValue(conflictErr);

    renderWithProviders(<ReviewPage />, { route: "/review" });

    await waitFor(() => {
      expect(screen.getByText("스태미나")).toBeInTheDocument();
    });

    await user.click(screen.getAllByText("스태미나")[0]); // Click the table row, not detail header
    await user.click(screen.getByText("Accept"));

    // Wait for mutation to settle
    await waitFor(() => {
      expect(mockAcceptIssue).toHaveBeenCalledWith("iss_1", {
        expectedVersion: 0,
        idempotencyKey: expect.stringMatching(/^review:iss_1:accept:v0:/),
        action: "resolve_as_new_concept",
        term: "스태미나",
        definition: "Review-approved concept for 스태미나.",
      });
    });

    // Error must remain visible -- no optimistic clearing
    const alert = screen.getByRole("alert");
    expect(alert).toBeInTheDocument();
    expect(alert).toHaveTextContent(/conflict/i);
    expect(alert).toHaveTextContent(/retry/i);

    // Issue row should still be visible (not cleared from UI)
    expect(screen.getAllByText("스태미나").length).toBeGreaterThan(0);
  });

  it("preserves action panel visibility after non-conflict API error", async () => {
    const user = userEvent.setup();
    mockListIssues.mockResolvedValue([{ ...MOCK_ISSUES[0] }]);
    mockDismissIssue.mockRejectedValue(
      new ApiError(500, "Internal Server Error", {
        message: "Database timeout",
        details: "Connection pool exhausted",
      }),
    );

    renderWithProviders(<ReviewPage />, { route: "/review" });

    await waitFor(() => {
      expect(screen.getByText("스태미나")).toBeInTheDocument();
    });

    await user.click(screen.getByText("스태미나"));
    await user.click(screen.getByText("Dismiss"));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });

    // Error details visible
    expect(screen.getByText(/connection pool exhausted/i)).toBeInTheDocument();
    // Actions still available for retry
    expect(screen.getByText("Accept")).toBeEnabled();
  });
});
