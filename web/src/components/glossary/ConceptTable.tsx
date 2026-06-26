import { useState, useMemo } from "react";
import type { Concept } from "../../lib/types";
import StatusBadge from "../shared/StatusBadge";

interface Props {
  concepts: readonly Concept[];
  onSelect?: (id: string) => void;
}

type StatusFilter = Concept["status"] | "all";

export default function ConceptTable({ concepts, onSelect }: Props) {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [tagFilter, setTagFilter] = useState("");

  const allTags = useMemo(() => {
    const set = new Set<string>();
    for (const c of concepts) for (const t of c.tags) set.add(t);
    return [...set].sort();
  }, [concepts]);

  const filtered = useMemo(() => {
    let list = concepts;
    if (statusFilter !== "all") {
      list = list.filter((c) => c.status === statusFilter);
    }
    if (tagFilter) {
      const t = tagFilter.toLowerCase();
      list = list.filter((c) =>
        c.tags.some((tag) => tag.toLowerCase().includes(t)),
      );
    }
    return list;
  }, [concepts, statusFilter, tagFilter]);

  return (
    <div className="concept-table-wrap">
      <div className="concept-table-filters">
        <fieldset>
          <legend className="filter-label">Status</legend>
          <div className="filter-group">
            {(["all", "active", "deprecated", "forbidden"] as const).map(
              (s) => (
                <button
                  key={s}
                  type="button"
                  className={`filter-chip ${statusFilter === s ? "active" : ""}`}
                  onClick={() => setStatusFilter(s)}
                >
                  {s === "all" ? "All" : s.charAt(0).toUpperCase() + s.slice(1)}
                </button>
              ),
            )}
          </div>
        </fieldset>

        <fieldset>
          <legend className="filter-label">Tag</legend>
          <input
            className="filter-input"
            placeholder="Filter by tag..."
            value={tagFilter}
            onChange={(e) => setTagFilter(e.target.value)}
            aria-label="Filter by tag"
            list="concept-tag-list"
          />
          {allTags.length > 0 && (
            <datalist id="concept-tag-list">
              {allTags.map((t) => (
                <option key={t} value={t} />
              ))}
            </datalist>
          )}
        </fieldset>
      </div>

      {filtered.length === 0 ? (
        <div className="text-muted">No concepts match the current filters.</div>
      ) : (
        <table className="data-table" aria-label="Glossary concepts">
          <thead>
            <tr>
              <th>Term</th>
              <th>Type</th>
              <th>Status</th>
              <th>Tags</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((c) => (
              <tr
                key={c.id}
                className={`data-row ${onSelect ? "clickable" : ""}`}
                onClick={() => onSelect?.(c.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSelect?.(c.id);
                  }
                }}
                tabIndex={onSelect ? 0 : undefined}
                aria-label={`View details for ${c.primaryTerm}`}
              >
                <td className="term-cell">{c.primaryTerm}</td>
                <td>
                  <span className="type-badge">{c.termType}</span>
                </td>
                <td>
                  <StatusBadge status={c.status} />
                </td>
                <td>
                  <div className="tag-list">
                    {c.tags.map((t) => (
                      <span key={t} className="tag-pill">{t}</span>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
