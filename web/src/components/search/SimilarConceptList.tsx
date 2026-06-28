import { useNavigate } from "react-router-dom";
import type { SimilarConceptMatch } from "../../lib/types";

interface Props {
  readonly matches: readonly SimilarConceptMatch[];
}

export default function SimilarConceptList({ matches }: Props) {
  const navigate = useNavigate();
  return (
    <ol className="similar-list">
      {matches.map((match, index) => (
        <li key={match.concept.id} className="similar-item">
          <button
            type="button"
            className="similar-card"
            onClick={() => navigate(`/glossary/${match.concept.id}`)}
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
