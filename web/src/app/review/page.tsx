import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { TermIssue } from "../../lib/types";
import IssueList from "../../components/review/IssueList";
import IssueDetail from "../../components/review/IssueDetail";
import ReviewActionPanel from "../../components/review/ReviewActionPanel";
import Loading from "../../components/shared/Loading";
import ErrorState from "../../components/shared/ErrorState";
import EmptyState from "../../components/shared/EmptyState";
import {
  issueQueries,
  useAcceptIssue,
  useDismissIssue,
  useResolveIssueAsNewConcept,
  useResolveIssueAsAlias,
  useResolveIssueAsForbidden,
} from "../../lib/queries";
import { ApiError } from "../../lib/api";
import { createIssueActionRequest, type ReviewActionKind } from "../../lib/reviewActions";
import type { IssueActionPayload, IssueActionRequest } from "../../lib/types";

type IssueActionVariables = {
  readonly id: string;
  readonly payload: IssueActionRequest;
};

type IssueActionMutate = (
  variables: IssueActionVariables,
) => Promise<IssueActionPayload>;

export default function ReviewPage() {
  const [selected, setSelected] = useState<TermIssue | null>(null);

  const listQuery = useQuery(issueQueries.list());

  /* Issue action mutations -- each calls exact backend endpoint */
  const acceptMutation = useAcceptIssue();
  const dismissMutation = useDismissIssue();
  const resolveNewConceptMutation = useResolveIssueAsNewConcept();
  const resolveAliasMutation = useResolveIssueAsAlias();
  const resolveForbiddenMutation = useResolveIssueAsForbidden();

  /* Determine which mutation is active and which error to show */
  const isMutating =
    acceptMutation.isPending ||
    dismissMutation.isPending ||
    resolveNewConceptMutation.isPending ||
    resolveAliasMutation.isPending ||
    resolveForbiddenMutation.isPending;

  const activeError =
    acceptMutation.error ||
    dismissMutation.error ||
    resolveNewConceptMutation.error ||
    resolveAliasMutation.error ||
    resolveForbiddenMutation.error;

  function handleSelect(issue: TermIssue) {
    setSelected(issue);
  }

  /*
   * Run a mutation and suppress the thrown rejection.
   * TanStack Query already captures the error in mutation.error,
   * which the ReviewActionPanel renders via the `error` prop.
   * Swallowing here prevents "unhandled promise rejection" noise in
   * Vitest/jsdom while keeping the error visible to the user.
   */
  function swallowMutationError(fn: () => Promise<unknown>): void {
    fn().catch(() => { /* intentional: error surfaces via TQ mutation.error */ });
  }

  function handleAccept() {
    runAction("accept", acceptMutation.mutateAsync);
  }

  function handleDismiss() {
    runAction("dismiss", dismissMutation.mutateAsync);
  }

  function handleResolveNewConcept() {
    runAction("new-concept", resolveNewConceptMutation.mutateAsync);
  }

  function handleResolveAlias() {
    runAction("alias", resolveAliasMutation.mutateAsync);
  }

  function handleResolveForbidden() {
    runAction("forbidden", resolveForbiddenMutation.mutateAsync);
  }

  function runAction(kind: ReviewActionKind, mutate: IssueActionMutate): void {
    if (!selected) return;
    const payload = createIssueActionRequest(selected, kind);
    swallowMutationError(async () => {
      const result = await mutate({ id: selected.id, payload });
      setSelected(result.issue);
    });
  }

  function mutationApiError(err: unknown): ApiError | null {
    return err instanceof ApiError ? err : null;
  }

  return (
    <div className="page-review">
      <header className="page-header">
        <h1 className="page-title">Review Queue</h1>
      </header>

      {listQuery.isLoading ? (
        <Loading label="Loading issues..." />
      ) : listQuery.isError ? (
        <ErrorState
          message={listQuery.error.message || "Failed to load issues"}
          onRetry={() => listQuery.refetch()}
        />
      ) : (
        <div className="review-layout">
          <div className="review-list-panel">
            <IssueList
              issues={listQuery.data ?? []}
              onSelect={handleSelect}
            />
          </div>

          <div className="review-detail-panel">
            {selected ? (
              <>
                <IssueDetail issue={selected} />
                <ReviewActionPanel
                  issue={selected}
                  onAccept={handleAccept}
                  onDismiss={handleDismiss}
                  onResolveAsNewConcept={handleResolveNewConcept}
                  onResolveAsAlias={handleResolveAlias}
                  onResolveAsForbidden={handleResolveForbidden}
                  isMutating={isMutating}
                  error={mutationApiError(activeError)}
                />
              </>
            ) : (
              <EmptyState message="Select an issue to review its details and actions." />
            )}
          </div>
        </div>
      )}
    </div>
  );
}
