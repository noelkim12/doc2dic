import type { ConceptStatus, IssueStatus } from "../../lib/types";

type Status = ConceptStatus | IssueStatus;

interface Props {
  status: Status;
}

const LABELS: Record<Status, string> = {
  active: "Active",
  deprecated: "Deprecated",
  forbidden: "Forbidden",
  open: "Open",
  resolved: "Resolved",
  dismissed: "Dismissed",
  failed: "Failed",
};

export default function StatusBadge({ status }: Props) {
  return (
    <span className={`badge badge-${status}`}>{LABELS[status]}</span>
  );
}
