import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import ConceptTable from "../../components/glossary/ConceptTable";
import ConceptForm from "../../components/glossary/ConceptForm";
import Loading from "../../components/shared/Loading";
import ErrorState from "../../components/shared/ErrorState";
import EmptyState from "../../components/shared/EmptyState";
import { conceptQueries, useCreateConcept } from "../../lib/queries";
import { ApiError } from "../../lib/api";

export default function GlossaryPage() {
  const navigate = useNavigate();
  const [showCreate, setShowCreate] = useState(false);

  const listQuery = useQuery(conceptQueries.list());
  const createMutation = useCreateConcept();

  function handleSelect(id: string) {
    navigate(`/glossary/${id}`);
  }

  function mutationApiError(err: unknown): ApiError | null {
    return err instanceof ApiError ? err : null;
  }

  return (
    <div className="page-glossary">
      <header className="page-header">
        <h1 className="page-title">Glossary</h1>
        <button
          className="btn-primary btn-sm"
          type="button"
          onClick={() => setShowCreate((v) => !v)}
          aria-expanded={showCreate}
        >
          {showCreate ? "Cancel" : "New Concept"}
        </button>
      </header>

      {showCreate && (
        <section className="create-section" aria-label="Create concept">
          <ConceptForm
            onSubmit={(data) => {
              void createMutation.mutateAsync(
                data as Parameters<NonNullable<typeof createMutation.mutate>>[0],
              );
            }}
            isSubmitting={createMutation.isPending}
            error={mutationApiError(createMutation.error)}
          />
        </section>
      )}

      {listQuery.isLoading ? (
        <Loading label="Loading concepts..." />
      ) : listQuery.isError ? (
        <ErrorState
          message={listQuery.error.message || "Failed to load concepts"}
          onRetry={() => listQuery.refetch()}
        />
      ) : listQuery.data?.length === 0 ? (
        <EmptyState message="No concepts yet. Create your first term!" />
      ) : (
        <ConceptTable concepts={listQuery.data ?? []} onSelect={handleSelect} />
      )}
    </div>
  );
}
