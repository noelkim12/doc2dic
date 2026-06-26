import { useMemo } from "react";
import type { TermType, GraphEdgeRelation } from "../../lib/types";

const ALL_TERM_TYPES: readonly TermType[] = [
  "mechanic",
  "resource",
  "state",
  "action",
  "stat",
  "entity",
  "rule",
  "ui-label",
  "lore",
  "unknown",
];

const ALL_RELATIONS: readonly GraphEdgeRelation[] = [
  "alias_of",
  "variant_of",
  "contradicts",
  "related_to",
  "depends_on",
  "part_of",
];

interface Props {
  termTypes: readonly TermType[];
  selectedTermTypes: readonly TermType[];
  relations: readonly GraphEdgeRelation[];
  selectedRelations: readonly GraphEdgeRelation[];
  onTermTypesChange: (selected: readonly TermType[]) => void;
  onRelationsChange: (selected: readonly GraphEdgeRelation[]) => void;
}

export default function GraphFilters({
  termTypes,
  selectedTermTypes,
  relations,
  selectedRelations,
  onTermTypesChange,
  onRelationsChange,
}: Props) {
  // Deduplicate defensively -- parent should deduplicate but component must be
  // robust against duplicate values that would produce duplicate React keys.
  const uniqueTermTypes = useMemo(
    () => [...new Set(termTypes)],
    [termTypes],
  );
  const uniqueRelations = useMemo(
    () => [...new Set(relations)],
    [relations],
  );

  function toggleTermType(t: TermType) {
    const next = selectedTermTypes.includes(t)
      ? selectedTermTypes.filter((s) => s !== t)
      : [...selectedTermTypes, t];
    onTermTypesChange(next);
  }

  function toggleRelation(r: GraphEdgeRelation) {
    const next = selectedRelations.includes(r)
      ? selectedRelations.filter((s) => s !== r)
      : [...selectedRelations, r];
    onRelationsChange(next);
  }

  return (
    <fieldset className="graph-filters" data-testid="graph-filters">
      <legend className="filter-label">Filters</legend>

      <div className="graph-filter-group">
        <span className="filter-label">Node Types</span>
        <div className="filter-group">
          {(uniqueTermTypes.length > 0 ? uniqueTermTypes : ALL_TERM_TYPES).map((t) => (
            <button
              key={t}
              type="button"
              className={`filter-chip ${selectedTermTypes.includes(t) ? "active" : ""}`}
              onClick={() => toggleTermType(t)}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      <div className="graph-filter-group">
        <span className="filter-label">Edge Relations</span>
        <div className="filter-group">
          {(uniqueRelations.length > 0 ? uniqueRelations : ALL_RELATIONS).map((r) => (
            <button
              key={r}
              type="button"
              className={`filter-chip ${selectedRelations.includes(r) ? "active" : ""}`}
              onClick={() => toggleRelation(r)}
            >
              {r}
            </button>
          ))}
        </div>
      </div>
    </fieldset>
  );
}

export { ALL_TERM_TYPES, ALL_RELATIONS };
