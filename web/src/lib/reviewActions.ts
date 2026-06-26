import type { IssueActionRequest, TermIssue } from "./types";

export type ReviewActionKind =
  | "accept"
  | "dismiss"
  | "new-concept"
  | "alias"
  | "forbidden";

const DEFAULT_DISMISS_REASON = "Dismissed from the review queue.";

export function createIssueActionRequest(
  issue: TermIssue,
  kind: ReviewActionKind,
): IssueActionRequest {
  const base = {
    expectedVersion: issue.version,
    idempotencyKey: createIdempotencyKey(issue, kind),
  };

  switch (kind) {
    case "accept":
      return createAcceptRequest(issue, base);
    case "dismiss":
      return { ...base, reason: DEFAULT_DISMISS_REASON };
    case "new-concept":
      return createNewConceptRequest(issue, base);
    case "alias":
      return createVariantRequest(issue, base, "resolve_as_alias");
    case "forbidden":
      return createVariantRequest(issue, base, "resolve_as_forbidden");
  }
}

function createAcceptRequest(
  issue: TermIssue,
  base: IssueActionBase,
): IssueActionRequest {
  switch (issue.issueType) {
    case "unknown_term":
    case "ambiguous_usage":
      return createNewConceptRequest(issue, base);
    case "forbidden_term":
      return createVariantRequest(issue, base, "resolve_as_forbidden");
    case "alias_candidate":
    case "same_meaning_different_term":
      return createVariantRequest(issue, base, "resolve_as_alias");
    case "conflicting_definition":
    case "same_term_different_meaning":
    case "graph_relation_candidate":
      return { ...base, action: "resolve_as_existing_concept", ...conceptField(issue) };
  }
}

function createNewConceptRequest(
  issue: TermIssue,
  base: IssueActionBase,
): IssueActionRequest {
  return {
    ...base,
    action: "resolve_as_new_concept",
    term: issue.surface,
    definition: `Review-approved concept for ${issue.surface}.`,
  };
}

function createVariantRequest(
  issue: TermIssue,
  base: IssueActionBase,
  action: "resolve_as_alias" | "resolve_as_forbidden",
): IssueActionRequest {
  return { ...base, action, ...conceptField(issue), variant: issue.surface };
}

function conceptField(issue: TermIssue): Pick<IssueActionRequest, "conceptId"> {
  const conceptId = issue.targetConceptId ?? issue.candidateConceptId;
  return conceptId === null || conceptId === undefined ? {} : { conceptId };
}

function createIdempotencyKey(issue: TermIssue, kind: ReviewActionKind): string {
  return `review:${issue.id}:${kind}:v${issue.version}:${crypto.randomUUID()}`;
}

type IssueActionBase = Pick<
  IssueActionRequest,
  "expectedVersion" | "idempotencyKey"
>;
