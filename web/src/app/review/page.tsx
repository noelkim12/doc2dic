import { useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import type { TermIssue } from "../../lib/types";
import IssueList from "../../components/review/IssueList";
import MasterDetail from "../../components/shared/MasterDetail";
import Loading from "../../components/shared/Loading";
import ErrorState from "../../components/shared/ErrorState";
import { issueQueries } from "../../lib/queries";

export default function ReviewPage() {
  const navigate = useNavigate();
  const { issueId } = useParams<{ issueId: string }>();

  const listQuery = useQuery(issueQueries.list());

  function handleSelect(issue: TermIssue) {
    navigate(`/review/${issue.id}`);
  }

  const listContent = listQuery.isLoading ? (
    <Loading label="Loading issues..." />
  ) : listQuery.isError ? (
    <ErrorState
      message={listQuery.error.message || "Failed to load issues"}
      onRetry={() => listQuery.refetch()}
    />
  ) : (
    <IssueList
      issues={listQuery.data ?? []}
      onSelect={handleSelect}
      selectedId={issueId}
    />
  );

  return (
    <div className="page-review">
      <header className="page-header">
        <h1 className="page-title">Review Queue</h1>
      </header>

      <MasterDetail list={listContent} />
    </div>
  );
}
