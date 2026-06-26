import type { TermIssue } from "../../lib/types";
import type { ApiError } from "../../lib/api";

interface Props {
  issue: TermIssue;
  onAccept?: () => void | Promise<void>;
  onDismiss?: () => void | Promise<void>;
  onResolveAsNewConcept?: () => void | Promise<void>;
  onResolveAsAlias?: () => void | Promise<void>;
  onResolveAsForbidden?: () => void | Promise<void>;
  isMutating?: boolean;
  error?: ApiError | null;
}

export default function ReviewActionPanel({
  issue,
  onAccept,
  onDismiss,
  onResolveAsNewConcept,
  onResolveAsAlias,
  onResolveAsForbidden,
  isMutating = false,
  error,
}: Props) {
  /* Determine if the issue is still actionable based on its current status */
  const isOpen = issue.status === "open";

  function extractErrorMessage(err: ApiError | null | undefined): string | null {
    if (!err) return null;
    return err.body?.details || err.body?.message || `${err.status}: ${err.statusText}`;
  }

  const errMsg = extractErrorMessage(error);

  return (
    <section className="review-action-panel" aria-label="Review actions">
      <h3 className="section-label">Actions</h3>

      {!isOpen && (
        <p className="text-muted action-disabled-note">
          This issue is{" "}
          <strong>{issue.status}</strong> and cannot be acted upon further.
        </p>
      )}

      <div className="action-buttons">
        <button
          type="button"
          className="btn-primary btn-sm"
          disabled={!isOpen || isMutating}
          onClick={onAccept}
          title="Accept the issue as valid"
        >
          Accept
        </button>

        <button
          type="button"
          className="btn-secondary btn-sm"
          disabled={!isOpen || isMutating}
          onClick={onDismiss}
          title="Dismiss this issue without resolution"
        >
          Dismiss
        </button>

        <button
          type="button"
          className="btn-secondary btn-sm"
          disabled={!isOpen || isMutating}
          onClick={onResolveAsNewConcept}
          title="Create a new glossary concept from this issue"
        >
          Resolve as New Concept
        </button>

        <button
          type="button"
          className="btn-secondary btn-sm"
          disabled={!isOpen || isMutating}
          onClick={onResolveAsAlias}
          title="Resolve as an alias to an existing concept"
        >
          Resolve as Alias
        </button>

        <button
          type="button"
          className="btn-secondary btn-sm action-danger"
          disabled={!isOpen || isMutating}
          onClick={onResolveAsForbidden}
          title="Mark this term as forbidden in the glossary"
        >
          Resolve as Forbidden
        </button>
      </div>

      {/* Stale-version / API conflict error remains visible; does not clear input */}
      {errMsg && (
        <div className="api-validation-error" role="alert">
          {error?.isConflict
            ? `Conflict: ${errMsg}. The issue may have been modified by another session. Please retry.`
            : errMsg}
        </div>
      )}
    </section>
  );
}
