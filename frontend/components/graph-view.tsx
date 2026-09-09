"use client";

import { useCallback, useMemo } from "react";
import {
  ReactFlow, Background, Controls, MiniMap,
  Node, Edge, useNodesState, useEdgesState,
  Handle, Position, NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Fact, Relationship } from "@/types";

// ---------------------------------------------------------------------------
// Node colours by attribute
// ---------------------------------------------------------------------------
const ATTR_COLORS: Record<string, string> = {
  Revenue: "#3b82f6", "Net Profit": "#10b981", EBITDA: "#8b5cf6",
  Employees: "#f59e0b", Warehouses: "#ef4444", Shipments: "#06b6d4",
  Coverage: "#84cc16", "Growth Rate": "#f97316", Margin: "#ec4899",
  Debt: "#6b7280", Cash: "#14b8a6", CEO: "#a855f7",
};

const REL_COLORS: Record<string, string> = {
  corroborated: "#10b981",
  contradiction: "#ef4444",
  reconciled: "#f59e0b",
  related: "#3b82f6",
};

// ---------------------------------------------------------------------------
// Custom fact node
// ---------------------------------------------------------------------------
function FactNode({ data }: NodeProps) {
  const d = data as any;
  const color = ATTR_COLORS[d.attribute] ?? "#6b7280";
  return (
    <div
      className="rounded-lg border-2 bg-background shadow-md px-3 py-2 min-w-[140px] max-w-[180px] cursor-pointer"
      style={{ borderColor: color }}
    >
      <Handle type="target" position={Position.Left} style={{ background: color }} />
      <p className="text-xs font-bold truncate" style={{ color }}>{d.attribute}</p>
      <p className="text-xs font-semibold truncate text-foreground mt-0.5">{d.entity}</p>
      <p className="text-xs font-mono text-muted-foreground truncate">
        {d.canonical_value || d.raw_value}
        {d.unit ? ` ${d.unit}` : ""}
      </p>
      {d.period && (
        <p className="text-xs text-muted-foreground font-mono">{d.period}</p>
      )}
      <Handle type="source" position={Position.Right} style={{ background: color }} />
    </div>
  );
}

const NODE_TYPES = { fact: FactNode };

// ---------------------------------------------------------------------------
// Layout: simple grid by entity column
// ---------------------------------------------------------------------------
function buildGraph(facts: Fact[], relationships: Relationship[], onNodeClick: (id: string) => void) {
  // Group facts by entity
  const entityGroups: Record<string, Fact[]> = {};
  for (const f of facts) {
    if (!entityGroups[f.entity]) entityGroups[f.entity] = [];
    entityGroups[f.entity].push(f);
  }

  const nodes: Node[] = [];
  const entityKeys = Object.keys(entityGroups);

  entityKeys.forEach((entity, colIdx) => {
    const colFacts = entityGroups[entity];
    colFacts.forEach((fact, rowIdx) => {
      nodes.push({
        id: fact.id,
        type: "fact",
        position: { x: colIdx * 240, y: rowIdx * 110 },
        data: { ...fact, onOpen: onNodeClick },
      });
    });
  });

  const edges: Edge[] = relationships.map((rel) => ({
    id: rel.id,
    source: rel.source_fact_id,
    target: rel.target_fact_id,
    label: rel.relationship_type,
    style: { stroke: REL_COLORS[rel.relationship_type] ?? "#6b7280", strokeWidth: 2 },
    labelStyle: { fontSize: 10, fill: REL_COLORS[rel.relationship_type] ?? "#6b7280", fontWeight: 600 },
    labelBgStyle: { fill: "var(--background)", fillOpacity: 0.8 },
    animated: rel.relationship_type === "corroborated",
  }));

  return { nodes, edges };
}

// ---------------------------------------------------------------------------
// Graph view
// ---------------------------------------------------------------------------
interface Props {
  facts: Fact[];
  relationships: Relationship[];
  onOpenFact: (id: string) => void;
}

export function GraphView({ facts, relationships, onOpenFact }: Props) {
  const { nodes: initNodes, edges: initEdges } = useMemo(
    () => buildGraph(facts, relationships, onOpenFact),
    [facts, relationships]
  );

  const [nodes, , onNodesChange] = useNodesState(initNodes);
  const [edges, , onEdgesChange] = useEdgesState(initEdges);

  const onNodeClick = useCallback((_: any, node: Node) => {
    onOpenFact(node.id);
  }, [onOpenFact]);

  if (facts.length === 0) {
    return (
      <div className="flex items-center justify-center h-[500px] text-muted-foreground">
        <div className="text-center">
          <p className="text-4xl mb-3">⬡</p>
          <p className="font-medium">No facts to graph</p>
          <p className="text-sm mt-1">Select a project with extracted facts</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-[600px] border rounded-xl overflow-hidden">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        nodeTypes={NODE_TYPES}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.3}
        maxZoom={2}
      >
        <Background gap={20} size={1} />
        <Controls />
        <MiniMap
          nodeColor={(n) => {
            const attr = (n.data as any)?.attribute ?? "";
            return ATTR_COLORS[attr] ?? "#6b7280";
          }}
          maskColor="rgba(0,0,0,0.1)"
        />
      </ReactFlow>

      {/* Legend */}
      <div className="absolute bottom-16 left-4 flex gap-3 flex-wrap pointer-events-none">
        {Object.entries(REL_COLORS).map(([type, color]) => (
          <span key={type} className="flex items-center gap-1 text-xs bg-background/90 px-2 py-0.5 rounded border">
            <span className="w-3 h-0.5 inline-block rounded" style={{ background: color }} />
            {type}
          </span>
        ))}
      </div>
    </div>
  );
}
