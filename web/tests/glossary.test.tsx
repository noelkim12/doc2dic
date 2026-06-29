import { describe, it, expect, vi, beforeEach } from "vitest";
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { Concept } from "../src/lib/types";
import ConceptTable from "../src/components/glossary/ConceptTable";
import ConceptForm from "../src/components/glossary/ConceptForm";
import VariantList from "../src/components/glossary/VariantList";
import RelationEditor from "../src/components/glossary/RelationEditor";
import GlossaryPage from "../src/app/glossary/page";
import ConceptDetailPage from "../src/app/glossary/[conceptId]/page";
import { ApiError } from "../src/lib/api";

/* ── Module-level apiClient mock ── */

const mockGetConcept = vi.fn();
const mockListConcepts = vi.fn();
const mockCreateConcept = vi.fn();
const mockPatchConcept = vi.fn();
const mockCreateVariant = vi.fn();
const mockDeleteConcept = vi.fn();

vi.mock("../src/lib/api", async () => {
  const actual = await vi.importActual("../src/lib/api");
  return {
    ...actual,
    apiClient: {
      ...(actual as Record<string, unknown>).apiClient,
      getConcept: (...args: unknown[]) => mockGetConcept(...args),
      listConcepts: (...args: unknown[]) => mockListConcepts(...args),
      createConcept: (...args: unknown[]) => mockCreateConcept(...args),
      patchConcept: (...args: unknown[]) => mockPatchConcept(...args),
      createTermVariant: (...args: unknown[]) => mockCreateVariant(...args),
      deleteConcept: (...args: unknown[]) => mockDeleteConcept(...args),
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

/* Render the detail page through a real route so useParams() resolves conceptId. */
function renderDetailRoute(conceptId: string) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/glossary/${conceptId}`]}>
        <Routes>
          <Route path="/glossary/:conceptId" element={<ConceptDetailPage />} />
          <Route path="/glossary" element={<div>Glossary list</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const MOCK_CONCEPTS: readonly Concept[] = [
  {
    id: "c_1",
    primaryTerm: "스태미나",
    definition: "A resource that limits action frequency.",
    termType: "stat",
    status: "active",
    tags: ["combat", "resource"],
    variants: ["v_1", "v_2"],
    createdAt: "2025-01-01T00:00:00Z",
    updatedAt: "2025-01-01T00:00:00Z",
  },
  {
    id: "c_2",
    primaryTerm: "Mana Pool",
    definition: "A resource for casting spells.",
    termType: "resource",
    status: "active",
    tags: ["magic"],
    variants: [],
    createdAt: "2025-01-02T00:00:00Z",
    updatedAt: "2025-01-02T00:00:00Z",
  },
  {
    id: "c_3",
    primaryTerm: "Banned Move",
    definition: "A move that is no longer allowed.",
    termType: "action",
    status: "forbidden",
    tags: ["combat"],
    variants: [],
    createdAt: "2025-01-03T00:00:00Z",
    updatedAt: "2025-01-03T00:00:00Z",
  },
];

/* ── Variant ID constants (contract-safe: Concept.variants is readonly string[]) ── */

const MOCK_VARIANT_IDS: readonly string[] = ["v_1", "v_2"];

/* ── ConceptTable ── */

describe("ConceptTable", () => {
  it("renders 스태미나 in the table", () => {
    renderWithProviders(<ConceptTable concepts={MOCK_CONCEPTS} />);
    expect(screen.getByText("스태미나")).toBeInTheDocument();
  });

  it("renders all concepts with their types and statuses", () => {
    renderWithProviders(<ConceptTable concepts={MOCK_CONCEPTS} />);
    expect(screen.getByText("Mana Pool")).toBeInTheDocument();
    expect(screen.getByText("Banned Move")).toBeInTheDocument();
    // "Active" appears in both filter buttons and status badges; check badge specifically
    const activeBadges = screen.getAllByText("Active");
    expect(activeBadges.length).toBeGreaterThanOrEqual(1);
    // "Forbidden" also appears in filter buttons
    const forbiddenBadges = screen.getAllByText("Forbidden");
    expect(forbiddenBadges.length).toBeGreaterThanOrEqual(1);
  });

  it("filters by tag combat showing only matching concepts", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ConceptTable concepts={MOCK_CONCEPTS} />);

    // Both 스태미나 and Banned Move have "combat" tag
    expect(screen.getAllByText("스태미나").length).toBeGreaterThanOrEqual(1);

    const tagInput = screen.getByLabelText(/filter by tag/i);
    await user.type(tagInput, "combat");

    // Should still show 스태미나 (has combat tag)
    expect(screen.getByText("스태미나")).toBeInTheDocument();
    // Mana Pool does NOT have combat tag - should be hidden
    expect(screen.queryAllByText("Mana Pool").length).toBe(0);
  });

  it("filters by status to show only active concepts", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ConceptTable concepts={MOCK_CONCEPTS} />);

    const activeBtn = screen.getByRole("button", { name: /active/i });
    await user.click(activeBtn);

    expect(screen.getByText("스태미나")).toBeInTheDocument();
    expect(screen.getByText("Mana Pool")).toBeInTheDocument();
    expect(screen.queryByText("Banned Move")).not.toBeInTheDocument();
  });

  it("calls onSelect when a row is clicked", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    renderWithProviders(
      <ConceptTable concepts={MOCK_CONCEPTS} onSelect={onSelect} />,
    );

    await user.click(screen.getByText("스태미나"));
    expect(onSelect).toHaveBeenCalledWith("c_1");
  });

  it("marks the selected row with the selected class", () => {
    const { container } = renderWithProviders(
      <ConceptTable concepts={MOCK_CONCEPTS} selectedId="c_1" />,
    );
    const selected = container.querySelector(".data-row.selected");
    expect(selected).not.toBeNull();
    expect(selected).toHaveTextContent("스태미나");
  });

  it("shows empty message when filters match nothing", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ConceptTable concepts={MOCK_CONCEPTS} />);

    const tagInput = screen.getByLabelText(/filter by tag/i);
    await user.type(tagInput, "nonexistent_tag_xyz");

    expect(
      screen.getByText(/no concepts match/i),
    ).toBeInTheDocument();
  });
});

/* ── ConceptForm ── */

describe("ConceptForm", () => {
  it("renders create form with empty fields by default", () => {
    renderWithProviders(
      <ConceptForm onSubmit={vi.fn()} />,
    );
    expect(screen.getByLabelText(/primary term/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/definition/i)).toBeInTheDocument();
    expect(screen.getByText("Create")).toBeInTheDocument();
  });

  it("renders edit form pre-filled with concept data", () => {
    renderWithProviders(
      <ConceptForm concept={MOCK_CONCEPTS[0]} onSubmit={vi.fn()} />,
    );
    const termInput = screen.getByLabelText(/primary term/i) as HTMLInputElement;
    expect(termInput.value).toBe("스태미나");
    expect(screen.getByText("Update")).toBeInTheDocument();
  });

  it("shows validation errors for empty required fields", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    renderWithProviders(<ConceptForm onSubmit={onSubmit} />);

    await user.click(screen.getByText("Create"));
    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByText(/primary term is required/i)).toBeInTheDocument();
    expect(screen.getByText(/definition is required/i)).toBeInTheDocument();
  });

  it("preserves unsaved form input on submission failure", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockRejectedValue(new Error("Server error"));
    renderWithProviders(<ConceptForm onSubmit={onSubmit} />);

    const termInput = screen.getByLabelText(/primary term/i);
    await user.type(termInput, "스태미나");

    const defInput = screen.getByLabelText(/definition/i);
    await user.type(defInput, "A stat resource.");

    await user.click(screen.getByText("Create"));

    // Form input should be preserved after failure
    expect((termInput as HTMLInputElement).value).toBe("스태미나");
    expect((defInput as HTMLInputElement).value).toBe("A stat resource.");
  });

  it("displays API validation error inline", () => {
    const apiErr = new ApiError(422, "Unprocessable Content", {
      message: "Duplicate term already exists",
      details: "A concept with this primary term already exists.",
    });
    renderWithProviders(
      <ConceptForm onSubmit={vi.fn()} error={apiErr} />,
    );
    expect(
      screen.getByText(/a concept with this primary term already exists/i),
    ).toBeInTheDocument();
  });
});

/* ── VariantList ── */

describe("VariantList", () => {
  it("renders variant IDs as labels", () => {
    renderWithProviders(<VariantList variantIds={MOCK_VARIANT_IDS} />);
    // VariantList renders each ID as a label -- contract-safe, no undefined fields
    expect(screen.getByText("v_1")).toBeInTheDocument();
    expect(screen.getByText("v_2")).toBeInTheDocument();
  });

  it("shows empty state when no variants", () => {
    renderWithProviders(<VariantList variantIds={[]} />);
    expect(screen.getByText(/no variants yet/i)).toBeInTheDocument();
  });

  it("submits alias via add form", async () => {
    const user = userEvent.setup();
    const onAddAlias = vi.fn().mockResolvedValue(undefined);
    renderWithProviders(
      <VariantList variantIds={MOCK_VARIANT_IDS} onAddAlias={onAddAlias} />,
    );

    const input = screen.getByLabelText(/alias label/i);
    await user.type(input, "Endurance");
    await user.click(screen.getByText(/add alias/i));

    expect(onAddAlias).toHaveBeenCalledWith("Endurance");
  });

  it("shows inline error when alias creation fails", () => {
    renderWithProviders(
      <VariantList
        variantIds={MOCK_VARIANT_IDS}
        onAddAlias={vi.fn()}
        error="Label conflicts with existing variant"
      />,
    );
    expect(
      screen.getByText(/label conflicts with existing variant/i),
    ).toBeInTheDocument();
  });
});

/* ── RelationEditor ── */

describe("RelationEditor", () => {
  it("renders all relation type buttons", () => {
    renderWithProviders(<RelationEditor />);
    expect(screen.getByText("alias of")).toBeInTheDocument();
    expect(screen.getByText("variant of")).toBeInTheDocument();
    expect(screen.getByText("contradicts")).toBeInTheDocument();
    expect(screen.getByText("related to")).toBeInTheDocument();
    expect(screen.getByText("depends on")).toBeInTheDocument();
    expect(screen.getByText("part of")).toBeInTheDocument();
  });

  it("highlights selected relation", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    renderWithProviders(<RelationEditor onSelect={onSelect} />);

    await user.click(screen.getByText("depends on"));
    expect(onSelect).toHaveBeenCalledWith("depends_on");
  });

  it("renders existing relations when provided", () => {
    const relations = [
      { targetLabel: "Health", relation: "depends_on" as const },
      { targetLabel: "Energy", relation: "related_to" as const },
    ];
    renderWithProviders(<RelationEditor relations={relations} />);
    expect(screen.getByText("Health")).toBeInTheDocument();
    expect(screen.getByText("Energy")).toBeInTheDocument();
  });
});

/* ── GlossaryPage (integration) ── */

describe("GlossaryPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading state while fetching concepts", () => {
    mockListConcepts.mockReturnValue(new Promise(() => {}));

    renderWithProviders(<GlossaryPage />, { route: "/glossary" });
    expect(screen.getByText(/loading concepts/i)).toBeInTheDocument();
  });

  it("shows concepts table after successful load", async () => {
    mockListConcepts.mockResolvedValue([...MOCK_CONCEPTS]);

    renderWithProviders(<GlossaryPage />, { route: "/glossary" });

    await waitFor(() => {
      expect(screen.getByText("스태미나")).toBeInTheDocument();
    });
    expect(screen.getByText("Glossary")).toBeInTheDocument();
  });

  it("shows error state when API fails", async () => {
    mockListConcepts.mockRejectedValue(new Error("Server Error"));

    renderWithProviders(<GlossaryPage />, { route: "/glossary" });

    await waitFor(() => {
      expect(screen.getByText(/failed to load|error/i)).toBeInTheDocument();
    });
  });

  it("toggles create form visibility", async () => {
    const user = userEvent.setup();
    mockListConcepts.mockResolvedValue([...MOCK_CONCEPTS]);

    renderWithProviders(<GlossaryPage />, { route: "/glossary" });

    await waitFor(() => {
      expect(screen.getByText("New Concept")).toBeInTheDocument();
    });

    await user.click(screen.getByText("New Concept"));
    expect(screen.getByLabelText(/create new concept/i)).toBeInTheDocument();

    await user.click(screen.getByText("Cancel"));
    expect(
      screen.queryByLabelText(/create new concept/i),
    ).not.toBeInTheDocument();
  });
});

/* ── ConceptDetailPage (integration) ── */

describe("ConceptDetailPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows concept detail with 스태미나", async () => {
    // Use contract-correct Concept shape: variants is readonly string[] (IDs only)
    mockGetConcept.mockResolvedValue({ ...MOCK_CONCEPTS[0] });

    renderWithProviders(<ConceptDetailPage />, {
      route: "/glossary/c_1",
    });

    await waitFor(() => {
      expect(screen.getByText("스태미나")).toBeInTheDocument();
    });
    expect(screen.getByText("A resource that limits action frequency.")).toBeInTheDocument();
    expect(screen.getByText("Variants")).toBeInTheDocument();
    expect(screen.getByText("Relations")).toBeInTheDocument();
    // Variant IDs render as labels (contract-safe, no undefined fields)
    expect(screen.getByText("v_1")).toBeInTheDocument();
    expect(screen.getByText("v_2")).toBeInTheDocument();
  });

  it("opens edit mode and preserves form values", async () => {
    const user = userEvent.setup();
    mockGetConcept.mockResolvedValue({ ...MOCK_CONCEPTS[0] });

    renderWithProviders(<ConceptDetailPage />, {
      route: "/glossary/c_1",
    });

    await waitFor(() => {
      expect(screen.getByText("Edit")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Edit"));

    const termInput = screen.getByLabelText(/primary term/i) as HTMLInputElement;
    expect(termInput.value).toBe("스태미나");
  });

  it("renders alias input and variant IDs in variant list", async () => {
    const user = userEvent.setup();
    mockGetConcept.mockResolvedValue({ ...MOCK_CONCEPTS[0] });

    renderWithProviders(<ConceptDetailPage />, {
      route: "/glossary/c_1",
    });

    // Verify variant IDs rendered (not expanded TermVariant objects)
    expect(await screen.findByText("v_1", { timeout: 3000 })).toBeInTheDocument();

    // Verify alias add form is present and interactive
    const aliasInput = screen.getByLabelText(/alias label/i);
    await user.type(aliasInput, "Endurance");
    expect((aliasInput as HTMLInputElement).value).toBe("Endurance");
  });

  it("handles no alert before mutation errors", async () => {
    mockGetConcept.mockResolvedValue({ ...MOCK_CONCEPTS[0] });

    renderWithProviders(<ConceptDetailPage />, {
      route: "/glossary/c_1",
    });

    await waitFor(() => {
      expect(screen.getByText("Edit")).toBeInTheDocument();
    });
    expect(screen.queryByRole("alert")).toBeNull();
  });

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

  it("requires confirmation before deleting a concept", async () => {
    const user = userEvent.setup();
    mockGetConcept.mockResolvedValue({ ...MOCK_CONCEPTS[0] });
    mockDeleteConcept.mockResolvedValue(undefined);

    renderDetailRoute("c_1");

    await waitFor(() => {
      expect(screen.getByText("Delete")).toBeInTheDocument();
    });

    // First click only reveals the confirmation, it must not delete yet.
    await user.click(screen.getByText("Delete"));
    expect(mockDeleteConcept).not.toHaveBeenCalled();
    expect(
      screen.getByRole("group", { name: /confirm delete concept/i }),
    ).toBeInTheDocument();
  });

  it("deletes the concept after confirmation and navigates to the list", async () => {
    const user = userEvent.setup();
    mockGetConcept.mockResolvedValue({ ...MOCK_CONCEPTS[0] });
    mockDeleteConcept.mockResolvedValue(undefined);

    renderDetailRoute("c_1");

    await waitFor(() => {
      expect(screen.getByText("Delete")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Delete"));
    await user.click(screen.getByText("Confirm Delete"));

    await waitFor(() => {
      expect(mockDeleteConcept).toHaveBeenCalledWith("c_1");
    });
    // After success the route changes to the glossary list.
    await waitFor(() => {
      expect(screen.getByText("Glossary list")).toBeInTheDocument();
    });
  });

  it("cancelling the delete confirmation does not delete", async () => {
    const user = userEvent.setup();
    mockGetConcept.mockResolvedValue({ ...MOCK_CONCEPTS[0] });
    mockDeleteConcept.mockResolvedValue(undefined);

    renderDetailRoute("c_1");

    await waitFor(() => {
      expect(screen.getByText("Delete")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Delete"));
    await user.click(screen.getByText("Cancel"));

    expect(mockDeleteConcept).not.toHaveBeenCalled();
    expect(screen.getByText("Delete")).toBeInTheDocument();
  });

  it("surfaces an error when deletion fails", async () => {
    const user = userEvent.setup();
    mockGetConcept.mockResolvedValue({ ...MOCK_CONCEPTS[0] });
    mockDeleteConcept.mockRejectedValue(
      new ApiError(409, "Conflict", {
        message: "Concept is referenced by documents",
        details: "Concept is referenced by documents",
      }),
    );

    renderDetailRoute("c_1");

    await waitFor(() => {
      expect(screen.getByText("Delete")).toBeInTheDocument();
    });

    await user.click(screen.getByText("Delete"));
    await user.click(screen.getByText("Confirm Delete"));

    await waitFor(() => {
      expect(
        screen.getByText(/concept is referenced by documents/i),
      ).toBeInTheDocument();
    });
  });
});
