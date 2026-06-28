import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { SimilarConceptMatch } from "../src/lib/types";
import { ApiError } from "../src/lib/api";
import SimilarConceptList from "../src/components/search/SimilarConceptList";
import SearchPage from "../src/app/search/page";

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return { ...actual, useNavigate: () => mockNavigate };
});

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

beforeEach(() => {
  mockNavigate.mockClear();
  mockSearch.mockClear();
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

  it("calls onSelect with the concept id on click", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(
      <MemoryRouter>
        <SimilarConceptList matches={MATCHES} onSelect={onSelect} />
      </MemoryRouter>,
    );
    await user.click(screen.getByText("스태미나"));
    expect(onSelect).toHaveBeenCalledWith("c_1");
  });

  it("marks the selected card as current", () => {
    render(
      <MemoryRouter>
        <SimilarConceptList matches={MATCHES} selectedId="c_1" />
      </MemoryRouter>,
    );
    expect(screen.getByRole("button")).toHaveAttribute("aria-current", "true");
  });
});

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

  it("shows the backend error reason when search fails", async () => {
    const user = userEvent.setup();
    mockSearch.mockRejectedValue(
      new ApiError(503, "Service Unavailable", {
        error: { code: "vector_search_unavailable", message: "vector search is disabled" },
      }),
    );
    renderPage(<SearchPage />);
    await user.type(screen.getByLabelText(/search text/i), "stamina");
    await user.click(screen.getByRole("button", { name: "Search" }));
    await waitFor(() =>
      expect(screen.getByText(/vector search is disabled/i)).toBeInTheDocument(),
    );
  });
});
