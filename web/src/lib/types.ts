export type TermType =
  | "mechanic"
  | "resource"
  | "state"
  | "action"
  | "stat"
  | "entity"
  | "rule"
  | "ui-label"
  | "lore"
  | "unknown";

export type ConceptStatus = "active" | "deprecated" | "forbidden";
export type TermVariantType = "primary" | "alias" | "forbidden" | "deprecated" | "abbreviation";
export type IssueStatus = "open" | "resolved" | "dismissed" | "failed";
export type ReviewAction =
  | "resolve_as_existing_concept"
  | "resolve_as_alias"
  | "resolve_as_forbidden"
  | "resolve_as_deprecated"
  | "resolve_as_new_concept"
  | "resolve_as_relation"
  | "dismiss"
  | "mark_failed";
export type IssueType =
  | "unknown_term"
  | "forbidden_term"
  | "conflicting_definition"
  | "alias_candidate"
  | "graph_relation_candidate"
  | "same_term_different_meaning"
  | "same_meaning_different_term"
  | "ambiguous_usage";
export type IssueEvidenceKind = "quote" | "occurrence" | "graph_relation" | "llm_rationale";
export type GraphEdgeRelation =
  | "alias_of"
  | "variant_of"
  | "contradicts"
  | "related_to"
  | "depends_on"
  | "part_of"
  | "derives_from"
  | "value_of";

export type Concept = {
  readonly id: string;
  readonly primaryTerm: string;
  readonly definition: string;
  readonly termType: TermType;
  readonly status: ConceptStatus;
  readonly tags: readonly string[];
  readonly variants: readonly string[];
  readonly createdAt: string;
  readonly updatedAt: string;
  readonly physicalName?: string;
};

export type SimilarConceptMatch = {
  readonly concept: Concept;
  readonly distance: number;
  readonly similarity: number;
};

export type TermVariant = {
  readonly id: string;
  readonly conceptId: string;
  readonly label: string;
  readonly variantType: TermVariantType;
  readonly status: ConceptStatus;
  readonly createdAt: string;
};

export type Document = {
  readonly id: string;
  readonly path: string;
  readonly title: string;
  readonly contentHash: string;
  readonly mimeType:
    | "text/markdown"
    | "text/plain"
    | "application/pdf"
    | "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
  readonly chunkIds: readonly string[];
  readonly analyzedAt: string;
};

export type DocumentChunk = {
  readonly id: string;
  readonly documentId: string;
  readonly sectionTitle: string;
  readonly ordinal: number;
  readonly textPreview: string;
  readonly contentHash: string;
};

export type TermOccurrence = {
  readonly id: string;
  readonly documentId: string;
  readonly chunkId: string;
  readonly conceptId: string | null;
  readonly surface: string;
  readonly offsetStart: number;
  readonly offsetEnd: number;
  readonly confidence: number;
};

export type IssueEvidence = {
  readonly id: string;
  readonly kind: IssueEvidenceKind;
  readonly sourceDocumentId: string;
  readonly chunkId?: string | null;
  readonly quote: string;
  readonly contextBefore?: string;
  readonly contextAfter?: string;
  readonly confidence: number;
};

export type TermIssue = {
  readonly id: string;
  readonly issueType: IssueType;
  readonly status: IssueStatus;
  readonly surface: string;
  readonly candidateConceptId?: string | null;
  readonly targetConceptId?: string | null;
  readonly evidence: readonly IssueEvidence[];
  readonly createdAt: string;
  readonly resolvedAt?: string | null;
  readonly version: number;
  readonly appliedIdempotencyKey?: string | null;
};

export type IssueActionRequest = {
  readonly expectedVersion: number;
  readonly idempotencyKey: string;
  readonly action?: ReviewAction;
  readonly term?: string;
  readonly definition?: string;
  readonly conceptId?: string;
  readonly variant?: string;
  readonly reason?: string;
  readonly sourceConceptId?: string;
  readonly targetConceptId?: string;
  readonly relationType?: GraphEdgeRelation;
};

export type IssueActionPayload = {
  readonly outcome: "applied" | "already_applied";
  readonly issue: TermIssue;
  readonly conceptId?: string | null;
  readonly variantId?: string | null;
  readonly relationId?: string | null;
};

export interface CreateConceptPayload {
  readonly primaryTerm: string;
  readonly definition: string;
  readonly termType: TermType;
  readonly status: ConceptStatus;
  readonly tags: readonly string[];
  readonly physicalName?: string;
}

export interface PatchConceptPayload {
  readonly primaryTerm?: string;
  readonly definition?: string;
  readonly termType?: TermType;
  readonly status?: ConceptStatus;
  readonly tags?: readonly string[];
  readonly physicalName?: string;
}

export interface CreateVariantPayload {
  readonly label: string;
  readonly variantType: TermVariantType;
  readonly status: ConceptStatus;
}

export type AppGraphNode = {
  readonly id: string;
  readonly label: string;
  readonly nodeType: "concept";
  readonly termType?: TermType;
};

export type AppGraphEdge = {
  readonly id: string;
  readonly source: string;
  readonly target: string;
  readonly relation: GraphEdgeRelation;
};

export type AppGraph = {
  readonly nodes: readonly AppGraphNode[];
  readonly edges: readonly AppGraphEdge[];
};

export type GraphSnapshot = {
  readonly id: string;
  readonly createdAt: string;
  readonly graph: AppGraph;
};

export type GraphifyProjectionDocument = {
  readonly path: string;
  readonly title: string;
  readonly body: string;
};

export type GraphifyProjection = {
  readonly graph: AppGraph;
  readonly documents: readonly GraphifyProjectionDocument[];
};

export type LLMCandidateEvidence = {
  readonly quote: string;
  readonly section_title?: string;
};

export type LLMTermCandidate = {
  readonly surface: string;
  readonly definition: string;
  readonly term_type: TermType;
  readonly tags: readonly string[];
  readonly evidence: readonly LLMCandidateEvidence[];
  readonly confidence: number;
};

export type LLMTermCandidatesOutput = {
  readonly candidates: readonly LLMTermCandidate[];
};

export type LLMConflictClassification = {
  readonly classification:
    | "same_concept"
    | "alias_candidate"
    | "same_term_different_meaning"
    | "same_meaning_different_term"
    | "new_concept"
    | "ambiguous";
  readonly target_concept_id?: string | null;
  readonly reason: string;
  readonly recommendation: string;
  readonly confidence: number;
};
