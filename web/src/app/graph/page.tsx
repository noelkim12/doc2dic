import { useState, useCallback, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import GraphCanvas from "../../components/graph/GraphCanvas";
import GraphFilters from "../../components/graph/GraphFilters";
import NodeDetailPanel from "../../components/graph/NodeDetailPanel";
import EdgeDetailPanel from "../../components/graph/EdgeDetailPanel";
import SnapshotSelector from "../../components/graph/SnapshotSelector";
import GraphifyExport from "../../components/graph/GraphifyExport";
import Loading from "../../components/shared/Loading";
import ErrorState from "../../components/shared/ErrorState";
import EmptyState from "../../components/shared/EmptyState";
import { graphQueries } from "../../lib/queries";
import { apiClient } from "../../lib/api";
import type { AppGraph, AppGraphNode, AppGraphEdge, TermType, GraphEdgeRelation } from "../../lib/types";

export default function GraphPage() {
  const [selectedSnapshotId, setSelectedSnapshotId] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<AppGraphNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<AppGraphEdge | null>(null);
  const [filteredTermTypes, setFilteredTermTypes] = useState<readonly TermType[]>([]);
  const [filteredRelations, setFilteredRelations] = useState<readonly GraphEdgeRelation[]>([]);

  /* Load current graph or selected snapshot */
  const currentQuery = useQuery(graphQueries.current());
  const snapshotsQuery = useQuery(graphQueries.snapshots());

  const snapshotQuery = useQuery({
    queryKey: [...graphQueries.all, "snapshot", "selected", selectedSnapshotId],
    queryFn: () => {
      if (!selectedSnapshotId) throw new Error("No snapshot selected");
      return apiClient.getGraphSnapshot(selectedSnapshotId);
    },
    enabled: !!selectedSnapshotId,
  });

  /* Resolve which graph data to display -- always normalize to AppGraph */
  const activeQuery = selectedSnapshotId ? snapshotQuery : currentQuery;
  const rawGraph = activeQuery.data ?? null;
  const graph: AppGraph | null = rawGraph && "graph" in rawGraph ? rawGraph.graph : rawGraph;
  const isLoading = activeQuery.isLoading || snapshotsQuery.isLoading;
  const error = activeQuery.error;

  const handleNodeSelect = useCallback((node: AppGraphNode | null) => {
    setSelectedNode(node);
  }, []);

  const handleEdgeSelect = useCallback((edge: AppGraphEdge | null) => {
    setSelectedEdge(edge);
  }, []);

  function handleRetry() {
    void currentQuery.refetch();
    void snapshotsQuery.refetch();
    if (selectedSnapshotId) void snapshotQuery.refetch();
  }

  /* Deduplicate filter values while preserving insertion order (MOCK_GRAPH has two "stat" nodes) */
  const uniqueTermTypes = useMemo(
    () => [...new Set(graph?.nodes.map((n) => n.termType).filter((t): t is TermType => !!t) ?? [])],
    [graph?.nodes],
  );
  const uniqueRelations = useMemo(
    () => [...new Set(graph?.edges.map((e) => e.relation) ?? [])],
    [graph?.edges],
  );

  return (
    <div className="page-graph">
      <header className="page-header">
        <h1 className="page-title">Graph</h1>
        <SnapshotSelector
          snapshots={snapshotsQuery.data ?? []}
          selectedSnapshotId={selectedSnapshotId}
          onSelect={setSelectedSnapshotId}
        />
      </header>

      <section className="graph-toolbar" aria-label="Graph filters">
        <GraphFilters
          termTypes={uniqueTermTypes}
          selectedTermTypes={filteredTermTypes}
          relations={uniqueRelations}
          selectedRelations={filteredRelations}
          onTermTypesChange={setFilteredTermTypes}
          onRelationsChange={setFilteredRelations}
        />
      </section>

      {isLoading ? (
        <Loading label="Loading graph..." />
      ) : error ? (
        <ErrorState
          message={error.message || "Failed to load graph"}
          onRetry={handleRetry}
        />
      ) : !graph || graph.nodes.length === 0 ? (
        <EmptyState message="No graph data yet. Analyze documents and create concepts to build the glossary graph." />
      ) : (
        <div className="graph-layout">
          <GraphCanvas
            graph={graph}
            selectedNode={selectedNode}
            selectedEdge={selectedEdge}
            onNodeSelect={handleNodeSelect}
            onEdgeSelect={handleEdgeSelect}
            filteredNodeTypes={filteredTermTypes}
            filteredRelations={filteredRelations}
          />

          {(selectedNode || selectedEdge) && (
            <div className="graph-panels">
              {selectedNode && (
                <NodeDetailPanel
                  node={selectedNode}
                  onClose={() => setSelectedNode(null)}
                />
              )}
              {selectedEdge && (
                <EdgeDetailPanel
                  edge={selectedEdge}
                  onClose={() => setSelectedEdge(null)}
                />
              )}
            </div>
          )}
        </div>
      )}

      <section className="graph-export-section" aria-label="Graph export">
        <GraphifyExport />
      </section>
    </div>
  );
}
