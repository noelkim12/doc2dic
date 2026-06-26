import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import DocumentUploader from "../../components/documents/DocumentUploader";
import DocumentViewer from "../../components/documents/DocumentViewer";
import Loading from "../../components/shared/Loading";
import ErrorState from "../../components/shared/ErrorState";
import EmptyState from "../../components/shared/EmptyState";
import {
  documentQueries,
  useAnalyzeDocumentPath,
} from "../../lib/queries";
import { apiClient } from "../../lib/api";
import { ApiError } from "../../lib/api";

export default function DocumentsPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const listQuery = useQuery(documentQueries.list());
  const analyzeMutation = useAnalyzeDocumentPath();

  /* Load selected document detail -- query key includes ID so switching documents never reuses stale cache */
  const detailQuery = useQuery({
    queryKey: [...documentQueries.details(), selectedId],
    queryFn: () => apiClient.getDocument(selectedId!),
    enabled: !!selectedId,
  });

  function handleSelect(id: string) {
    setSelectedId(id);
  }

  function extractError(err: unknown): string | null {
    if (err instanceof ApiError) {
      return err.body?.details || err.body?.message || null;
    }
    if (err instanceof Error) return err.message;
    return null;
  }

  return (
    <div className="page-documents">
      <header className="page-header">
        <h1 className="page-title">Documents</h1>
      </header>

      <section className="analyze-section" aria-label="Analyze document">
        <DocumentUploader
          onAnalyze={(path) =>
            analyzeMutation.mutateAsync(path).catch(() => {
              /* intentional: error surfaces via analyzeMutation.error */
            })
          }
          isAnalyzing={analyzeMutation.isPending}
          error={extractError(analyzeMutation.error)}
        />
      </section>

      {listQuery.isLoading ? (
        <Loading label="Loading documents..." />
      ) : listQuery.isError ? (
        <ErrorState
          message={listQuery.error.message || "Failed to load documents"}
          onRetry={() => listQuery.refetch()}
        />
      ) : listQuery.data?.length === 0 ? (
        <EmptyState message="No documents yet. Analyze a file path to get started." />
      ) : (
        <div className="documents-layout">
          <div className="document-list-panel">
            <table
              className="data-table"
              aria-label="Documents"
            >
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Type</th>
                  <th>Analyzed</th>
                </tr>
              </thead>
              <tbody>
                {listQuery.data?.map((doc) => (
                  <tr
                    key={doc.id}
                    className={`data-row clickable ${
                      selectedId === doc.id ? "selected" : ""
                    }`}
                    onClick={() => handleSelect(doc.id)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.preventDefault();
                        handleSelect(doc.id);
                      }
                    }}
                    tabIndex={0}
                    aria-label={`View ${doc.title}`}
                  >
                    <td className="term-cell">{doc.title}</td>
                    <td>
                      <span className="type-badge">
                        {doc.mimeType.split("/")[1]}
                      </span>
                    </td>
                    <td className="text-muted">
                      {doc.analyzedAt
                        ? new Date(doc.analyzedAt).toLocaleDateString()
                        : "--"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {detailQuery.isLoading ? (
            <Loading label="Loading document..." />
          ) : detailQuery.data ? (
            <DocumentViewer document={detailQuery.data} />
          ) : selectedId ? (
            <ErrorState
              message="Failed to load document details"
              onRetry={() => detailQuery.refetch()}
            />
          ) : null}
        </div>
      )}
    </div>
  );
}
