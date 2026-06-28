import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import IssueDetail from "../../../components/review/IssueDetail";
import ReviewActionPanel from "../../../components/review/ReviewActionPanel";
import EmptyState from "../../../components/shared/EmptyState";
import Loading from "../../../components/shared/Loading";
import ErrorState from "../../../components/shared/ErrorState";
import {
  issueQueries,
  useAcceptIssue,
  useDismissIssue,
  useResolveIssueAsNewConcept,
  useResolveIssueAsAlias,
  useResolveIssueAsForbidden,
} from "../../../lib/queries";
import { ApiError } from "../../../lib/api";
import {
  createIssueActionRequest,
  type ReviewActionKind,
} from "../../../lib/reviewActions";
import type {
  IssueActionPayload,
  IssueActionRequest,
} from "../../../lib/types";

type IssueActionMutate = (variables: {
  readonly id: string;
  readonly payload: IssueActionRequest;
}) => Promise<IssueActionPayload>;

export default function IssueDetailPage() {
  const { issueId } = useParams<{ issueId: string }>();

  /*
   * The selected issue is derived from the shared list cache rather than a
   * separate detail fetch: the list already holds full issue objects, and
   * issue mutations invalidate the list, so the panel re-derives the updated
   * issue (version/status) after each action.
   */
  const listQuery = useQuery(issueQueries.list());
  const selected = listQuery.data?.find((i) => i.id === issueId) ?? null;

  const acceptMutation = useAcceptIssue();
  const dismissMutation = useDismissIssue();
  const resolveNewConceptMutation = useResolveIssueAsNewConcept();
  const resolveAliasMutation = useResolveIssueAsAlias();
  const resolveForbiddenMutation = useResolveIssueAsForbidden();

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

  function runAction(kind: ReviewActionKind, mutate: IssueActionMutate): void {
    if (!selected) return;
    const payload = createIssueActionRequest(selected, kind);
    /* Error surfaces via the active mutation's error; list refetches on invalidate. */
    mutate({ id: selected.id, payload }).catch(() => {
      /* intentional: error surfaces via mutation.error */
    });
  }

  function mutationApiError(err: unknown): ApiError | null {
    return err instanceof ApiError ? err : null;
  }

  if (listQuery.isLoading) return <Loading label="Loading issue..." />;
  if (listQuery.isError) {
    return (
      <ErrorState
        message={listQuery.error.message || "Failed to load issue"}
        onRetry={() => listQuery.refetch()}
      />
    );
  }
  if (!selected) {
    return <EmptyState message="This issue is no longer in the queue." />;
  }

  return (
    <>
      <IssueDetail issue={selected} />
      <ReviewActionPanel
        issue={selected}
        onAccept={() => runAction("accept", acceptMutation.mutateAsync)}
        onDismiss={() => runAction("dismiss", dismissMutation.mutateAsync)}
        onResolveAsNewConcept={() =>
          runAction("new-concept", resolveNewConceptMutation.mutateAsync)
        }
        onResolveAsAlias={() =>
          runAction("alias", resolveAliasMutation.mutateAsync)
        }
        onResolveAsForbidden={() =>
          runAction("forbidden", resolveForbiddenMutation.mutateAsync)
        }
        isMutating={isMutating}
        error={mutationApiError(activeError)}
      />
    </>
  );
}
