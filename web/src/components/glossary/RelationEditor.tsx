import type { GraphEdgeRelation } from "../../lib/types";
import { useState } from "react";

const ALL_RELATIONS: readonly GraphEdgeRelation[] = [
  "alias_of",
  "variant_of",
  "contradicts",
  "related_to",
  "depends_on",
  "part_of",
  "derives_from",
  "value_of",
];

interface Props {
  relations?: readonly { targetLabel: string; relation: GraphEdgeRelation }[];
  onSelect?: (relation: GraphEdgeRelation, targetId?: string) => void;
  disabled?: boolean;
}

export default function RelationEditor({
  relations = [],
  onSelect,
  disabled = false,
}: Props) {
  const [selected, setSelected] = useState<GraphEdgeRelation | null>(null);

  function handleSelect(r: GraphEdgeRelation) {
    if (disabled) return;
    setSelected(r);
    onSelect?.(r);
  }

  return (
    <div className="relation-editor">
      <h3 className="relation-editor-title">Relations</h3>

      {relations.length > 0 && (
        <ul className="relation-list">
          {relations.map((r, i) => (
            <li key={`${r.targetLabel}-${i}`} className="relation-item">
              <span className="relation-type badge">{r.relation.replace(/_/g, " ")}</span>
              <span className="relation-target">{r.targetLabel}</span>
            </li>
          ))}
        </ul>
      )}

      <fieldset className="relation-picker" disabled={disabled}>
        <legend className="filter-label">Add relation</legend>
        <div className="relation-options">
          {ALL_RELATIONS.map((r) => (
            <button
              key={r}
              type="button"
              className={`relation-chip ${selected === r ? "selected" : ""}`}
              onClick={() => handleSelect(r)}
            >
              {r.replace(/_/g, " ")}
            </button>
          ))}
        </div>
      </fieldset>
    </div>
  );
}
