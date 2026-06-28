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
