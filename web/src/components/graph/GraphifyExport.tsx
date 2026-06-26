import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { apiClient } from "../../lib/api";
import type { GraphifyProjection } from "../../lib/types";

interface Props {
  onExportComplete?: (projection: GraphifyProjection) => void;
}

export default function GraphifyExport({ onExportComplete }: Props) {
  const [error, setError] = useState<string | null>(null);

  const exportMutation = useMutation({
    mutationFn: () => apiClient.exportGraphify(),
    onSuccess: (data) => {
      setError(null);
      onExportComplete?.(data);
    },
    onError: (err: unknown) => {
      const msg =
        err instanceof Error ? err.message : "Graphify export failed";
      setError(msg);
    },
  });

  return (
    <section className="graphify-export-section" data-testid="graphify-export">
      <h4 className="filter-label">Graphify Export</h4>
      <p className="graphify-note">
        Export the current graph projection as Graphify-compatible output.
        The Graphify runtime is optional; this endpoint always returns a
        deterministic projection.
      </p>
      <button
        type="button"
        className="btn-primary btn-sm"
        onClick={() => {
          exportMutation.mutate();
          /* intentional: error surfaces via mutation.error */
        }}
        disabled={exportMutation.isPending}
      >
        {exportMutation.isPending ? "Exporting..." : "Export Projection"}
      </button>
      {exportMutation.data && !exportMutation.isPending && (
        <div className="graphify-success">
          <p className="text-muted">
            Exported {exportMutation.data.graph.nodes.length} nodes,{" "}
            {exportMutation.data.graph.edges.length} edges,{" "}
            {exportMutation.data.documents.length} documents.
          </p>
        </div>
      )}
      {error && (
        <p className="state-error" style={{ marginTop: "var(--space-sm)" }}>
          {error}
        </p>
      )}
    </section>
  );
}
