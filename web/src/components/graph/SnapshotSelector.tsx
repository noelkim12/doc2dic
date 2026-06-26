import type { GraphSnapshot } from "../../lib/types";

interface Props {
  snapshots: readonly GraphSnapshot[];
  selectedSnapshotId: string | null;
  onSelect: (id: string | null) => void;
}

export default function SnapshotSelector({
  snapshots,
  selectedSnapshotId,
  onSelect,
}: Props) {
  if (snapshots.length === 0) return null;

  return (
    <div className="graph-snapshot-selector" data-testid="snapshot-selector">
      <label className="filter-label" htmlFor="graph-snapshot-select">
        Snapshot
      </label>
      <select
        id="graph-snapshot-select"
        className="field-input field-select graph-snapshot-select"
        value={selectedSnapshotId ?? ""}
        onChange={(e) => {
          const val = e.target.value;
          onSelect(val === "" ? null : val);
        }}
      >
        <option value="">Current Graph</option>
        {snapshots.map((s) => (
          <option key={s.id} value={s.id}>
            {s.createdAt} ({s.id.slice(0, 12)}...)
          </option>
        ))}
      </select>
      {selectedSnapshotId && (
        <button
          type="button"
          className="btn-secondary btn-sm"
          onClick={() => onSelect(null)}
        >
          Show Current
        </button>
      )}
    </div>
  );
}
