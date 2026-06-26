import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DocumentsPage from "../src/app/documents/page";
import ReviewPage from "../src/app/review/page";
import GraphPage from "../src/app/graph/page";
import { ApiError } from "../src/lib/api";
import type { AppGraph } from "../src/lib/types";

const mockListDocuments = vi.fn();
const mockGetDocument = vi.fn();
const mockAnalyzeDocumentPath = vi.fn();
const mockListIssues = vi.fn();
const mockGetCurrentGraph = vi.fn();
const mockListGraphSnapshots = vi.fn();
const mockGetGraphSnapshot = vi.fn();
const mockExportGraphify = vi.fn();

vi.mock("../src/lib/api", async () => {
  const actual = await vi.importActual<typeof import("../src/lib/api")>("../src/lib/api");
  return {
    ...actual,
    apiClient: {
      ...actual.apiClient,
      listDocuments: () => mockListDocuments(),
      getDocument: (id: string) => mockGetDocument(id),
      analyzeDocumentPath: (path: string) => mockAnalyzeDocumentPath(path),
      listIssues: () => mockListIssues(),
      getCurrentGraph: () => mockGetCurrentGraph(),
      listGraphSnapshots: () => mockListGraphSnapshots(),
      getGraphSnapshot: (id: string) => mockGetGraphSnapshot(id),
      exportGraphify: () => mockExportGraphify(),
    },
  };
});

const RAW_DOCUMENT_TEXT = "raw document text " + "경직 상태 원문 ".repeat(90);
const EMPTY_GRAPH: AppGraph = { nodes: [], edges: [] };

function renderWithProviders(ui: React.ReactElement, route: string) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("backend failure empty and error states", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows a documents empty state when the backend returns no documents", async () => {
    mockListDocuments.mockResolvedValue([]);

    renderWithProviders(<DocumentsPage />, "/documents");

    expect(await screen.findByText(/no documents yet/i)).toBeInTheDocument();
  });

  it("renders bounded document errors without raw backend payloads", async () => {
    mockListDocuments.mockRejectedValue(
      new ApiError(500, "Internal Server Error", {
        message: "Failed to load documents",
        details: RAW_DOCUMENT_TEXT,
        rawDocument: RAW_DOCUMENT_TEXT,
      }),
    );

    renderWithProviders(<DocumentsPage />, "/documents");

    await waitFor(() => {
      expect(screen.getByText(/api 500/i)).toBeInTheDocument();
    });
    expect(screen.queryByText(/경직 상태 원문 경직 상태 원문 경직 상태 원문/)).toBeNull();
  });

  it("keeps review queue usable when issue loading fails", async () => {
    mockListIssues.mockRejectedValue(new Error("database temporarily unavailable"));

    renderWithProviders(<ReviewPage />, "/review");

    expect(await screen.findByText(/database temporarily unavailable/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("shows graph empty state and keeps Graphify unavailable as a local warning", async () => {
    const user = userEvent.setup();
    mockGetCurrentGraph.mockResolvedValue(EMPTY_GRAPH);
    mockListGraphSnapshots.mockResolvedValue([]);
    mockExportGraphify.mockRejectedValue(new Error("Graphify runtime unavailable"));

    renderWithProviders(<GraphPage />, "/graph");

    expect(await screen.findByText(/no graph data yet/i)).toBeInTheDocument();
    await user.click(screen.getByText("Export Projection"));
    expect(await screen.findByText(/graphify runtime unavailable/i)).toBeInTheDocument();
  });
});
