import type { TermOccurrence } from "../../lib/types";
import ConfidenceBadge from "../shared/ConfidenceBadge";

interface Props {
  occurrences: readonly TermOccurrence[];
}

export default function OccurrencePanel({ occurrences }: Props) {
  if (occurrences.length === 0) {
    return (
      <p className="text-muted">No term occurrences found in this document.</p>
    );
  }

  return (
    <div className="occurrence-panel">
      <h3 className="section-label">
        Occurrences ({occurrences.length})
      </h3>
      <ul className="occurrence-list">
        {occurrences.map((o) => (
          <li key={o.id} className="occurrence-item">
          <div className="occurrence-header">
            <span style={{ fontWeight: 600 }}>{o.surface}</span>
            <ConfidenceBadge confidence={o.confidence} />
          </div>
            {o.chunkId && (
              <span className="occurrence-chunk text-muted">
                Chunk: {o.chunkId}
              </span>
            )}
            {o.conceptId && (
              <span className="occurrence-concept text-muted">
                Concept: {o.conceptId}
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
