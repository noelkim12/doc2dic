import type { AppGraphEdge } from "../../lib/types";

interface Props {
  edge: AppGraphEdge | null;
  onClose: () => void;
}

export default function EdgeDetailPanel({ edge, onClose }: Props) {
  if (!edge) return null;

  return (
    <aside className="graph-detail-panel" data-testid="edge-detail-panel">
      <header className="graph-detail-header">
        <h4 className="graph-detail-title">Edge Relation</h4>
        {onClose && (
          <button
            type="button"
            className="btn-secondary btn-sm"
            onClick={onClose}
            aria-label="Close detail panel"
          >
            Close
          </button>
        )}
      </header>
      <dl className="graph-detail-list">
        <dt>Source</dt>
        <dd className="text-muted">{edge.source}</dd>
        <dt>Relation</dt>
        <dd><span className="type-badge">{edge.relation}</span></dd>
        <dt>Target</dt>
        <dd className="text-muted">{edge.target}</dd>
        <dt>Edge ID</dt>
        <dd className="graph-edge-id">{edge.id}</dd>
      </dl>
    </aside>
  );
}
