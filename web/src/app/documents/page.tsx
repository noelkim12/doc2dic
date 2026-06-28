import { useQuery } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import DocumentUploader from "../../components/documents/DocumentUploader";
import MasterDetail from "../../components/shared/MasterDetail";
import Loading from "../../components/shared/Loading";
import ErrorState from "../../components/shared/ErrorState";
import EmptyState from "../../components/shared/EmptyState";
import { documentQueries, useAnalyzeDocumentPath } from "../../lib/queries";
import { ApiError } from "../../lib/api";

export default function DocumentsPage() {
  const navigate = useNavigate();
  const { documentId } = useParams<{ documentId: string }>();

  const listQuery = useQuery(documentQueries.list());
  const analyzeMutation = useAnalyzeDocumentPath();

  function handleSelect(id: string) {
    navigate(`/documents/${id}`);
  }

  function extractError(err: unknown): string | null {
    if (err instanceof ApiError) {
      return err.body?.details || err.body?.message || null;
    }
    if (err instanceof Error) return err.message;
    return null;
  }

  const listContent = listQuery.isLoading ? (
    <Loading label="Loading documents..." />
  ) : listQuery.isError ? (
    <ErrorState
      message={listQuery.error.message || "Failed to load documents"}
      onRetry={() => listQuery.refetch()}
    />
  ) : listQuery.data?.length === 0 ? (
    <EmptyState message="No documents yet. Analyze a file path to get started." />
  ) : (
    <table className="data-table" aria-label="Documents">
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
              documentId === doc.id ? "selected" : ""
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
              <span className="type-badge">{doc.mimeType.split("/")[1]}</span>
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
  );

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

      <MasterDetail list={listContent} />
    </div>
  );
}
