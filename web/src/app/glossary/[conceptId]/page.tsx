import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams, Link } from "react-router-dom";
import ConceptForm from "../../../components/glossary/ConceptForm";
import VariantList from "../../../components/glossary/VariantList";
import RelationEditor from "../../../components/glossary/RelationEditor";
import StatusBadge from "../../../components/shared/StatusBadge";
import Loading from "../../../components/shared/Loading";
import ErrorState from "../../../components/shared/ErrorState";
import {
  conceptQueries,
  usePatchConcept,
  useCreateVariant,
} from "../../../lib/queries";
import type { Concept, TermType } from "../../../lib/types";
import { ApiError } from "../../../lib/api";

export default function ConceptDetailPage() {
  const { conceptId } = useParams<{ conceptId: string }>();
  const [editing, setEditing] = useState(false);

  const detailQuery = useQuery(conceptQueries.detail(conceptId!));
  const patchMutation = usePatchConcept();
  const addAliasMutation = useCreateVariant();

  const concept = detailQuery.data;

  async function handleUpdate(data: {
    primaryTerm: string;
    definition: string;
    termType: TermType;
    status: Concept["status"];
    tags: readonly string[];
  }) {
    if (!conceptId) return;
    await patchMutation.mutateAsync({
      id: conceptId,
      data: {
        primaryTerm: data.primaryTerm,
        definition: data.definition,
        termType: data.termType,
        status: data.status,
        tags: [...data.tags],
      },
    });
    setEditing(false);
  }

  async function handleAddAlias(label: string) {
    if (!conceptId) return;
    await addAliasMutation.mutateAsync({
      conceptId,
      data: { label, variantType: "alias", status: "active" },
    });
  }

  function extractErrorMessage(err: unknown): string | null {
    if (err instanceof ApiError) {
      return err.body?.details || err.body?.message || null;
    }
    if (err instanceof Error) {
      return err.message || null;
    }
    return null;
  }

  if (detailQuery.isLoading) return <Loading label="Loading concept..." />;
  if (detailQuery.isError) {
    return (
      <ErrorState
        message={detailQuery.error.message || "Failed to load concept"}
        onRetry={() => detailQuery.refetch()}
      />
    );
  }
  if (!concept) return null;

  return (
    <div className="page-concept-detail">
      <header className="page-header">
        <Link to="/glossary" className="back-link">
          &larr; Back to Glossary
        </Link>
        <h1 className="page-title">{concept.primaryTerm}</h1>
        <div className="concept-header-meta">
          <StatusBadge status={concept.status} />
          <span className="type-badge">{concept.termType}</span>
        </div>
      </header>

      <section className="concept-detail-body">
        <div className="definition-block">
          <h2 className="section-label">Definition</h2>
          <p className="definition-text">{concept.definition || "No definition."}</p>
        </div>

        {concept?.tags && concept.tags.length > 0 && (
          <div className="tags-block">
            <h2 className="section-label">Tags</h2>
            <div className="tag-list">
              {concept.tags.map((t) => (
                <span key={t} className="tag-pill">{t}</span>
              ))}
            </div>
          </div>
        )}
      </section>

      {editing ? (
        <section className="edit-section" aria-label="Edit concept">
          <ConceptForm
            concept={concept}
            onSubmit={handleUpdate}
            isSubmitting={patchMutation.isPending}
            error={patchMutation.error as ApiError | null}
          />
          <button
            type="button"
            className="btn-secondary btn-sm"
            onClick={() => setEditing(false)}
          >
            Cancel Edit
          </button>
        </section>
      ) : (
        <div className="detail-actions">
          <button
            type="button"
            className="btn-primary btn-sm"
            onClick={() => setEditing(true)}
          >
            Edit
          </button>
        </div>
      )}

      <VariantList
        variantIds={concept.variants}
        onAddAlias={handleAddAlias}
        isAdding={addAliasMutation.isPending}
        error={extractErrorMessage(addAliasMutation.error)}
      />

      <RelationEditor />
    </div>
  );
}
