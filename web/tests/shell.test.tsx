import { describe, it, expect, vi } from "vitest";
import React from "react";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import AppLayout from "../src/app/layout";
import { API_ENDPOINTS, ApiError, apiClient } from "../src/lib/api";
import * as queryModule from "../src/lib/queries";
import Loading from "../src/components/shared/Loading";
import ErrorState from "../src/components/shared/ErrorState";
import EmptyState from "../src/components/shared/EmptyState";

function renderWithProviders(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("shell smoke tests", () => {
  it("renders brand heading", () => {
    renderWithProviders(<AppLayout />);
    expect(screen.getByText("Doc2Dic")).toBeInTheDocument();
  });

  it("renders all nav links", () => {
    renderWithProviders(<AppLayout />);
    const nav = screen.getByRole("navigation");
    const expected = ["Home", "Glossary", "Documents", "Review", "Graph", "Settings"];
    for (const label of expected) {
      expect(nav).toHaveTextContent(label);
    }
  });

  it("nav links have correct href targets", () => {
    renderWithProviders(<AppLayout />);
    const glossary = screen.getByText("Glossary").closest("a");
    expect(glossary?.getAttribute("href")).toBe("/glossary");
    const review = screen.getByText("Review").closest("a");
    expect(review?.getAttribute("href")).toBe("/review");
  });

  it("renders main content area", () => {
    renderWithProviders(<AppLayout />);
    const main = document.querySelector("main.app-main");
    expect(main).not.toBeNull();
  });
});

describe("API endpoint constants match OpenAPI contract", () => {
  it("health endpoint", () => {
    expect(API_ENDPOINTS.health).toBe("/api/health");
  });

  it("concepts collection endpoint", () => {
    expect(API_ENDPOINTS.concepts).toBe("/api/concepts");
  });

  it("concept detail endpoint pattern", () => {
    expect(API_ENDPOINTS.concept("concept_abc")).toBe(
      "/api/concepts/concept_abc",
    );
  });

  it("documents collection endpoint", () => {
    expect(API_ENDPOINTS.documents).toBe("/api/documents");
  });

  it("issues collection endpoint", () => {
    expect(API_ENDPOINTS.issues).toBe("/api/issues");
  });

  it("issue action endpoints", () => {
    expect(API_ENDPOINTS.issueAccept("issue_1")).toBe(
      "/api/issues/issue_1/accept",
    );
    expect(API_ENDPOINTS.issueDismiss("issue_1")).toBe(
      "/api/issues/issue_1/dismiss",
    );
    expect(API_ENDPOINTS.issueResolveNewConcept("issue_1")).toBe(
      "/api/issues/issue_1/resolve-as-new-concept",
    );
    expect(API_ENDPOINTS.issueResolveAlias("issue_1")).toBe(
      "/api/issues/issue_1/resolve-as-alias",
    );
    expect(API_ENDPOINTS.issueResolveForbidden("issue_1")).toBe(
      "/api/issues/issue_1/resolve-as-forbidden",
    );
  });

  it("posts issue action body to the exact endpoint", async () => {
    const payload = {
      expectedVersion: 7,
      idempotencyKey: "review-issue-1-dismiss-7",
      reason: "duplicate finding",
    };
    const responseBody = {
      outcome: "applied",
      issue: {
        id: "issue_1",
        issueType: "unknown_term",
        status: "dismissed",
        surface: "Dash",
        evidence: [],
        createdAt: "2026-06-25T00:00:00Z",
        resolvedAt: "2026-06-25T00:05:00Z",
        version: 8,
        appliedIdempotencyKey: "review-issue-1-dismiss-7",
      },
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(responseBody), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    try {
      await apiClient.dismissIssue("issue_1", payload);

      expect(fetchMock).toHaveBeenCalledWith("/api/issues/issue_1/dismiss", {
        headers: { "Content-Type": "application/json" },
        method: "POST",
        body: JSON.stringify(payload),
      });
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("graph endpoints", () => {
    expect(API_ENDPOINTS.currentGraph).toBe("/api/graphs/current");
    expect(API_ENDPOINTS.rebuildGraph).toBe("/api/graphs/rebuild");
    expect(API_ENDPOINTS.graphSnapshots).toBe("/api/graphs/snapshots");
    expect(API_ENDPOINTS.exportGraphify).toBe("/api/graphs/graphify/export");
  });

  it("search endpoints", () => {
    expect(API_ENDPOINTS.searchConcepts).toBe("/api/search/concepts");
    expect(API_ENDPOINTS.searchSimilarConcepts).toBe(
      "/api/search/similar-concepts",
    );
  });
});

describe("ApiError typed error class", () => {
  it("exposes status and safe body without raw response", () => {
    const err = new ApiError(404, "Not Found", { message: "missing" });
    expect(err.status).toBe(404);
    expect(err.statusText).toBe("Not Found");
    expect(err.body).toEqual({ message: "missing" });
    expect(err.name).toBe("ApiError");
    expect(err.message).toBe("API 404: Not Found");
  });

  it("classifies error categories", () => {
    expect(new ApiError(400, "", null).isClientError).toBe(true);
    expect(new ApiError(409, "", null).isConflict).toBe(true);
    expect(new ApiError(404, "", null).isNotFound).toBe(true);
    expect(new ApiError(500, "", null).isServerError).toBe(true);
    expect(new ApiError(200, "", null).isClientError).toBe(false);
  });

  it("stores null body for non-object error responses", () => {
    const err = new ApiError(500, "Internal Error", null);
    expect(err.body).toBeNull();
  });

  it("does not leak raw array bodies", () => {
    const err = new ApiError(500, "", ["line1", "line2", "huge document text..."]);
    expect(err.body).toBeNull();
  });

  it("truncates details field to safe bound", () => {
    const longText = "x".repeat(1000);
    const err = new ApiError(400, "", { details: longText });
    expect(err.body?.details?.length).toBeLessThanOrEqual(500);
  });

  it("only extracts known safe fields (message, code, details)", () => {
    const err = new ApiError(403, "", {
      message: "forbidden",
      code: "FORBIDDEN",
      secret: "should not appear",
      rawDocument: "full document text here...",
    });
    expect(err.body?.message).toBe("forbidden");
    expect(err.body?.code).toBe("FORBIDDEN");
    expect((err.body as Record<string, unknown>).secret).toBeUndefined();
    expect((err.body as Record<string, unknown>).rawDocument).toBeUndefined();
  });
});

describe("query options export structure", () => {
  it("exports concept query factories", () => {
    expect(typeof queryModule.conceptQueries.list).toBe("function");
    expect(typeof queryModule.conceptQueries.detail).toBe("function");
  });

  it("exports document query factories", () => {
    expect(typeof queryModule.documentQueries.list).toBe("function");
    expect(typeof queryModule.documentQueries.detail).toBe("function");
    expect(typeof queryModule.documentQueries.occurrences).toBe("function");
  });

  it("exports issue query factories", () => {
    expect(typeof queryModule.issueQueries.list).toBe("function");
    expect(typeof queryModule.issueQueries.detail).toBe("function");
  });

  it("exports graph query factories", () => {
    expect(typeof queryModule.graphQueries.current).toBe("function");
    expect(typeof queryModule.graphQueries.snapshots).toBe("function");
  });

  it("exports search query factories", () => {
    expect(typeof queryModule.searchQueries.concepts).toBe("function");
    expect(typeof queryModule.searchQueries.similarConcepts).toBe("function");
  });

  it("queryOptions returns queryKey and queryFn", () => {
    const opts = queryModule.conceptQueries.list();
    expect(opts.queryKey).toBeDefined();
    expect(opts.queryFn).toBeDefined();
  });
});

describe("Loading helper component", () => {
  it("renders default label", () => {
    render(<Loading />);
    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("renders custom label", () => {
    render(<Loading label="Fetching concepts..." />);
    expect(screen.getByText("Fetching concepts...")).toBeInTheDocument();
  });

  it("uses state-loading CSS class", () => {
    const { container } = render(<Loading />);
    expect(container.firstChild).toHaveClass("state-loading");
  });
});

describe("ErrorState helper component", () => {
  it("renders error message", () => {
    render(<ErrorState message="Something went wrong" />);
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
  });

  it("uses state-error CSS class", () => {
    const { container } = render(<ErrorState message="err" />);
    expect(container.firstChild).toHaveClass("state-error");
  });

  it("shows retry button when onRetry is provided", () => {
    const onRetry = vi.fn();
    render(<ErrorState message="fail" onRetry={onRetry} />);
    const retryOpts = { name: /retry/i };
    const btn = screen.getByRole("button", retryOpts);
    expect(btn).toBeInTheDocument();
  });

  it("calls onRetry when retry button clicked", () => {
    const onRetry = vi.fn();
    render(<ErrorState message="fail" onRetry={onRetry} />);
    const retryOpts = { name: /retry/i };
    screen.getByRole("button", retryOpts).click();
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("hides retry button when onRetry is omitted", () => {
    render(<ErrorState message="fail" />);
    expect(screen.queryByRole("button")).toBeNull();
  });
});

describe("EmptyState helper component", () => {
  it("renders empty message", () => {
    render(<EmptyState message="No concepts found" />);
    expect(screen.getByText("No concepts found")).toBeInTheDocument();
  });

  it("uses state-empty CSS class", () => {
    const { container } = render(<EmptyState message="empty" />);
    expect(container.firstChild).toHaveClass("state-empty");
  });
});
