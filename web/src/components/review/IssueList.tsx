import { useState, useMemo } from "react";
import type { TermIssue, IssueStatus, IssueType } from "../../lib/types";
import StatusBadge from "../shared/StatusBadge";

interface Props {
  issues: readonly TermIssue[];
  onSelect?: (issue: TermIssue) => void;
  selectedId?: string;
}

const ISSUE_TYPE_LABELS: Record<IssueType, string> = {
  unknown_term: "Unknown Term",
  forbidden_term: "Forbidden Term",
  conflicting_definition: "Conflicting Definition",
  alias_candidate: "Alias Candidate",
  graph_relation_candidate: "Graph Relation",
  same_term_different_meaning: "Same Term, Different Meaning",
  same_meaning_different_term: "Same Meaning, Different Term",
  ambiguous_usage: "Ambiguous Usage",
};

const STATUS_OPTIONS: readonly (IssueStatus | "all")[] = [
  "all",
  "open",
  "resolved",
  "dismissed",
  "failed",
];

export default function IssueList({ issues, onSelect, selectedId }: Props) {
  const [statusFilter, setStatusFilter] = useState<IssueStatus | "all">("all");
  const [typeFilter, setTypeFilter] = useState<IssueType | "all">("all");

  const allTypes = useMemo(() => {
    const set = new Set<IssueType>();
    for (const i of issues) set.add(i.issueType);
    return [...set].sort();
  }, [issues]);

  const filtered = useMemo(() => {
    let list = issues;
    if (statusFilter !== "all") {
      list = list.filter((i) => i.status === statusFilter);
    }
    if (typeFilter !== "all") {
      list = list.filter((i) => i.issueType === typeFilter);
    }
    return list;
  }, [issues, statusFilter, typeFilter]);

  return (
    <div className="issue-list-wrap">
      <div className="issue-list-filters">
        <fieldset>
          <legend className="filter-label">Status</legend>
          <div className="filter-group">
            {STATUS_OPTIONS.map((s) => (
              <button
                key={s}
                type="button"
                className={`filter-chip ${statusFilter === s ? "active" : ""}`}
                onClick={() => setStatusFilter(s)}
              >
                {s === "all" ? "All" : s.charAt(0).toUpperCase() + s.slice(1)}
              </button>
            ))}
          </div>
        </fieldset>

        {allTypes.length > 1 && (
          <fieldset>
            <legend className="filter-label">Type</legend>
            <div className="filter-group">
              <button
                type="button"
                className={`filter-chip ${typeFilter === "all" ? "active" : ""}`}
                onClick={() => setTypeFilter("all")}
              >
                All
              </button>
              {allTypes.map((t) => (
                <button
                  key={t}
                  type="button"
                  className={`filter-chip ${typeFilter === t ? "active" : ""}`}
                  onClick={() => setTypeFilter(t)}
                >
                  {ISSUE_TYPE_LABELS[t]}
                </button>
              ))}
            </div>
          </fieldset>
        )}
      </div>

      {filtered.length === 0 ? (
        <div className="text-muted">
          {issues.length === 0
            ? "No issues found. Analyze a document to detect term issues."
            : "No issues match the current filters."}
        </div>
      ) : (
        <table className="data-table" aria-label="Review issues">
          <thead>
            <tr>
              <th>Surface</th>
              <th>Type</th>
              <th>Status</th>
              <th>Evidence</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((issue) => (
              <tr
                key={issue.id}
                className={`data-row ${onSelect ? "clickable" : ""} ${
                  selectedId === issue.id ? "selected" : ""
                }`}
                onClick={() => onSelect?.(issue)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    onSelect?.(issue);
                  }
                }}
                tabIndex={onSelect ? 0 : undefined}
                aria-label={`View issue: ${issue.surface}`}
              >
                <td className="term-cell">{issue.surface}</td>
                <td>
                  <span className="type-badge">
                    {ISSUE_TYPE_LABELS[issue.issueType]}
                  </span>
                </td>
                <td>
                  <StatusBadge status={issue.status} />
                </td>
                <td className="text-muted">
                  {issue.evidence.length} item{issue.evidence.length !== 1 ? "s" : ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
