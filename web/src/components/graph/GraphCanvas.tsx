import { useCallback, useEffect, useMemo, useRef } from "react";
import {
  ReactFlow,
  type Node,
  type Edge,
  type NodeMouseHandler,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  BackgroundVariant,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { AppGraph, AppGraphNode, AppGraphEdge, TermType, GraphEdgeRelation } from "../../lib/types";

interface Props {
  graph: AppGraph | null;
  selectedNode: AppGraphNode | null;
  selectedEdge: AppGraphEdge | null;
  onNodeSelect: (node: AppGraphNode | null) => void;
  onEdgeSelect: (edge: AppGraphEdge | null) => void;
  filteredNodeTypes?: readonly TermType[];
  filteredRelations?: readonly GraphEdgeRelation[];
}

const NODE_TYPE = "concept";

function toFlowNodes(
  nodes: readonly AppGraphNode[],
  filters?: readonly TermType[],
): Node[] {
  const filtered = filters && filters.length > 0
    ? nodes.filter((n) => !n.termType || filters.includes(n.termType))
    : nodes;
  return filtered.map((n, i) => ({
    id: n.id,
    type: NODE_TYPE,
    position: { x: (i % 5) * 220, y: Math.floor(i / 5) * 160 },
    data: { label: n.label, termType: n.termType, nodeType: n.nodeType },
  }));
}

function toFlowEdges(
  edges: readonly AppGraphEdge[],
  allNodes: readonly AppGraphNode[],
  filters?: readonly GraphEdgeRelation[],
): Edge[] {
  const nodeIds = new Set(allNodes.map((n) => n.id));
  const filtered = filters && filters.length > 0
    ? edges.filter((e) => filters.includes(e.relation))
    : edges;
  return filtered
    .filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target))
    .map((e) => ({
      id: e.id,
      source: e.source,
      target: e.target,
      label: e.relation,
      type: "smoothstep",
      animated: e.relation === "contradicts",
      data: { relation: e.relation },
    }));
}

export default function GraphCanvas({
  graph,
  onNodeSelect,
  onEdgeSelect,
  filteredNodeTypes,
  filteredRelations,
}: Props) {
  const flowNodes = useMemo(
    () => (graph ? toFlowNodes(graph.nodes, filteredNodeTypes) : []),
    [graph, filteredNodeTypes],
  );

  const flowEdges = useMemo(
    () => (graph ? toFlowEdges(graph.edges, graph.nodes, filteredRelations) : []),
    [graph, graph?.nodes, filteredRelations],
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(flowNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(flowEdges);

  // Track previous derived data to avoid redundant setNodes/setEdges calls.
  const prevFlowNodesRef = useRef(flowNodes);
  const prevFlowEdgesRef = useRef(flowEdges);

  useEffect(() => {
    // Only sync when the derived arrays actually changed (reference equality check
    // works because useMemo returns the same array reference when inputs are stable).
    if (flowNodes !== prevFlowNodesRef.current) {
      prevFlowNodesRef.current = flowNodes;
      setNodes(flowNodes);
    }
    if (flowEdges !== prevFlowEdgesRef.current) {
      prevFlowEdgesRef.current = flowEdges;
      setEdges(flowEdges);
    }
  }, [flowNodes, flowEdges, setNodes, setEdges]);

  const handleNodeClick: NodeMouseHandler = (_event, node) => {
    const appNode = graph?.nodes.find((n) => n.id === node.id) ?? null;
    onNodeSelect(appNode);
    onEdgeSelect(null);
  };

  const handleEdgeClick = useCallback(
    (_event: React.MouseEvent, edge: Edge) => {
      const appEdge = graph?.edges.find((e) => e.id === edge.id) ?? null;
      onEdgeSelect(appEdge);
      onNodeSelect(null);
    },
    [graph, onNodeSelect, onEdgeSelect],
  );

  const handlePaneClick = useCallback(() => {
    onNodeSelect(null);
    onEdgeSelect(null);
  }, [onNodeSelect, onEdgeSelect]);

  if (!graph) return null;

  return (
    <div data-testid="graph-canvas" className="graph-canvas-wrap">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        onEdgeClick={handleEdgeClick}
        onPaneClick={handlePaneClick}
        nodeTypes={{ [NODE_TYPE]: ConceptNode }}
        fitView
        attributionPosition="bottom-left"
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1} />
        <Controls />
        <MiniMap nodeStrokeWidth={3} pannable zoomable />
      </ReactFlow>
    </div>
  );
}

/* ── Custom concept node renderer ── */

function ConceptNode({ data }: { data: { label: string; termType?: TermType; nodeType: string } }) {
  return (
    <div className={`graph-node ${data.termType ? `graph-node--${data.termType}` : ""}`} data-testid="graph-concept-node">
      <span className="graph-node__label">{data.label}</span>
      {data.termType && <span className="graph-node__type">{data.termType}</span>}
    </div>
  );
}
