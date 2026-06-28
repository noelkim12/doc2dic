import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import DocumentViewer from "../../../components/documents/DocumentViewer";
import OccurrencePanel from "../../../components/documents/OccurrencePanel";
import Loading from "../../../components/shared/Loading";
import ErrorState from "../../../components/shared/ErrorState";
import { apiClient } from "../../../lib/api";
import { documentQueries } from "../../../lib/queries";

export default function DocumentDetailPage() {
  const { documentId } = useParams<{ documentId: string }>();

  /* Query key includes route documentId so different URLs never share stale cache */
  const detailQuery = useQuery({
    queryKey: [...documentQueries.details(), documentId],
    queryFn: () => apiClient.getDocument(documentId!),
    enabled: !!documentId,
  });

  const occurrenceQuery = useQuery({
    queryKey: ["documents", "occurrences", documentId],
    queryFn: () => apiClient.listDocumentOccurrences(documentId!),
    enabled: !!documentId,
  });

  const document = detailQuery.data;

  if (detailQuery.isLoading) return <Loading label="Loading document..." />;
  if (detailQuery.isError) {
    return (
      <ErrorState
        message={detailQuery.error.message || "Failed to load document"}
        onRetry={() => detailQuery.refetch()}
      />
    );
  }
  if (!document) return null;

  return (
    <div className="document-detail-panel">
      <DocumentViewer document={document} />

      {occurrenceQuery.isLoading ? (
        <Loading label="Loading occurrences..." />
      ) : occurrenceQuery.isError ? (
        <ErrorState
          message={occurrenceQuery.error.message || "Failed to load occurrences"}
          onRetry={() => occurrenceQuery.refetch()}
        />
      ) : occurrenceQuery.data ? (
        <OccurrencePanel occurrences={occurrenceQuery.data} />
      ) : null}
    </div>
  );
}
