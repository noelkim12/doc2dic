import { describe, it, expect } from "vitest";
import type { Concept, TermIssue, AppGraph } from "../src/lib/types";

describe("type import boundary", () => {
  it("imports contract types from lib/types.ts", () => {
    const concept: Concept = {
      id: "concept_test_1",
      primaryTerm: "Test",
      definition: "A test concept",
      termType: "entity",
      status: "active",
      tags: ["test"],
      variants: [],
      createdAt: "2026-01-01T00:00:00Z",
      updatedAt: "2026-01-01T00:00:00Z",
    };
    expect(concept.primaryTerm).toBe("Test");
  });

  it("imports issue types from lib/types.ts", () => {
    const issue: TermIssue = {
      id: "issue_test_1",
      issueType: "unknown_term",
      status: "open",
      surface: "foo",
      evidence: [],
      createdAt: "2026-01-01T00:00:00Z",
    };
    expect(issue.status).toBe("open");
  });

  it("imports graph types from lib/types.ts", () => {
    const graph: AppGraph = {
      nodes: [
        {
          id: "concept_test_1",
          label: "Test",
          nodeType: "concept",
          termType: "entity",
        },
      ],
      edges: [],
    };
    expect(graph.nodes).toHaveLength(1);
  });
});


