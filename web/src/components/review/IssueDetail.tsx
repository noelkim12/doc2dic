import type { TermIssue, IssueEvidenceKind } from "../../lib/types";
import StatusBadge from "../shared/StatusBadge";
import ConfidenceBadge from "../shared/ConfidenceBadge";

interface Props {
  issue: TermIssue;
}

const EVIDENCE_KIND_LABELS: Record<IssueEvidenceKind, string> = {
  quote: "Quote",
  occurrence: "Occurrence",
  graph_relation: "Graph Relation",
  llm_rationale: "LLM Rationale",
};

export default function IssueDetail({ issue }: Props) {
  return (
    <div className="issue-detail">
      <header className="issue-detail-header">
        <h2 className="issue-detail-surface">{issue.surface}</h2>
        <div className="issue-detail-meta">
          <StatusBadge status={issue.status} />
          <span className="type-badge">{issue.issueType}</span>
          <span className="text-muted issue-date">
            {new Date(issue.createdAt).toLocaleDateString()}
          </span>
        </div>
      </header>

      {issue.candidateConceptId && (
        <p className="issue-candidate">
          Candidate concept:{" "}
          <code className="issue-candidate-id">{issue.candidateConceptId}</code>
        </p>
      )}

      {issue.targetConceptId && (
        <p className="issue-target">
          Target concept:{" "}
          <code className="issue-target-id">{issue.targetConceptId}</code>
        </p>
      )}

      {issue.evidence.length > 0 && (
        <section className="issue-evidence" aria-label="Issue evidence">
          <h3 className="section-label">
            Evidence ({issue.evidence.length})
          </h3>
          <ul className="evidence-list">
            {issue.evidence.map((ev) => (
              <li key={ev.id} className="evidence-item">
                <div className="evidence-item-header">
                  <span className={`badge badge-${ev.kind}`}>
                    {EVIDENCE_KIND_LABELS[ev.kind]}
                  </span>
                  {ev.confidence > 0 && (
                    <ConfidenceBadge confidence={ev.confidence} />
                  )}
                </div>

                {/* Bounded quote display -- never render full raw documents */}
                <blockquote className="evidence-quote">
                  {ev.quote}
                </blockquote>

                {(ev.contextBefore || ev.contextAfter) && (
                  <div className="evidence-context text-muted">
                    {ev.contextBefore && (
                      <span className="context-before">
                        ...{ev.contextBefore}
                      </span>
                    )}
                    {ev.contextAfter && (
                      <span className="context-after">
                        {ev.contextAfter}...
                      </span>
                    )}
                  </div>
                )}

                {ev.sourceDocumentId && (
                  <span className="evidence-source text-muted">
                    Source: {ev.sourceDocumentId}
                    {ev.chunkId ? ` / ${ev.chunkId}` : ""}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {issue.resolvedAt && (
        <p className="text-muted issue-resolved">
          Resolved: {new Date(issue.resolvedAt).toLocaleString()}
        </p>
      )}
    </div>
  );
}
