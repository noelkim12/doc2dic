import type { SimilarConceptMatch } from "../../lib/types";

interface Props {
  readonly matches: readonly SimilarConceptMatch[];
  readonly onSelect?: (id: string) => void;
  readonly selectedId?: string;
}

export default function SimilarConceptList({
  matches,
  onSelect,
  selectedId,
}: Props) {
  return (
    <ol className="similar-list">
      {matches.map((match, index) => (
        <li key={match.concept.id} className="similar-item">
          <button
            type="button"
            className={`similar-card ${
              selectedId === match.concept.id ? "selected" : ""
            }`}
            aria-current={selectedId === match.concept.id ? "true" : undefined}
            onClick={() => onSelect?.(match.concept.id)}
          >
            <span className="similar-rank">{index + 1}</span>
            <span className="similar-term">{match.concept.primaryTerm}</span>
            <span className="similar-definition">
              {match.concept.definition}
            </span>
            <span className="similar-score">
              {Math.round(match.similarity * 100)}%
            </span>
          </button>
        </li>
      ))}
    </ol>
  );
}
