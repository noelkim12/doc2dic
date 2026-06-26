import type { AppGraphNode } from "../../lib/types";

interface Props {
  node: AppGraphNode | null;
  onClose: () => void;
}

export default function NodeDetailPanel({ node, onClose }: Props) {
  if (!node) return null;

  return (
    <aside className="graph-detail-panel" data-testid="node-detail-panel">
      <header className="graph-detail-header">
        <h4 className="graph-detail-title">{node.label}</h4>
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
        <dt>ID</dt>
        <dd className="text-muted">{node.id}</dd>
        <dt>Node Type</dt>
        <dd><span className="type-badge">{node.nodeType}</span></dd>
        {node.termType && (
          <>
            <dt>Term Type</dt>
            <dd><span className="type-badge">{node.termType}</span></dd>
          </>
        )}
      </dl>
    </aside>
  );
}
