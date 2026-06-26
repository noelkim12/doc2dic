import { useState } from "react";

interface Props {
  /** Variant IDs as returned by the frozen Concept type (readonly string[]) */
  variantIds: readonly string[];
  onAddAlias?: (label: string) => void | Promise<void>;
  isAdding?: boolean;
  error?: string | null;
}

export default function VariantList({
  variantIds,
  onAddAlias,
  isAdding = false,
  error,
}: Props) {
  const [newLabel, setNewLabel] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = newLabel.trim();
    if (!trimmed || !onAddAlias) return;
    await onAddAlias(trimmed);
    setNewLabel("");
  }

  return (
    <div className="variant-list">
      <h3 className="variant-list-title">Variants</h3>

      {!variantIds || variantIds.length === 0 ? (
        <p className="text-muted">No variants yet.</p>
      ) : (
        <ul className="variant-items">
          {variantIds.map((id) => (
            <li key={id} className="variant-item">
              <span className="variant-label">{id}</span>
              <span className="badge badge-id">ID</span>
            </li>
          ))}
        </ul>
      )}

      {onAddAlias && (
        <form
          className="variant-add-form"
          onSubmit={handleSubmit}
          aria-label="Add alias"
        >
          <input
            className="field-input variant-input"
            type="text"
            value={newLabel}
            onChange={(e) => setNewLabel(e.target.value)}
            placeholder="New alias..."
            disabled={isAdding}
            aria-label="Alias label"
          />
          <button
            type="submit"
            className="btn-secondary btn-sm"
            disabled={isAdding || !newLabel.trim()}
          >
            {isAdding ? "Adding..." : "Add Alias"}
          </button>
        </form>
      )}

      {error && (
        <span className="field-error" role="alert">
          {error}
        </span>
      )}
    </div>
  );
}
