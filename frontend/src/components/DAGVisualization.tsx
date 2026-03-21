import { useCallback, useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { TaskDef, TaskInstance } from "../api/client";
import { getStateColor } from "../utils/state";

interface Props {
  tasks: TaskDef[];
  taskInstances?: TaskInstance[];
}

/** Compute a layered layout using topological depth. */
function layoutNodes(tasks: TaskDef[]): Node[] {
  const depths: Record<string, number> = {};

  function getDepth(taskId: string, visited: Set<string>): number {
    if (depths[taskId] !== undefined) return depths[taskId];
    if (visited.has(taskId)) return 0;
    visited.add(taskId);
    const task = tasks.find((t) => t.task_id === taskId);
    if (!task || task.depends_on.length === 0) {
      depths[taskId] = 0;
      return 0;
    }
    const maxParent = Math.max(
      ...task.depends_on.map((d) => getDepth(d, visited))
    );
    depths[taskId] = maxParent + 1;
    return depths[taskId];
  }

  tasks.forEach((t) => getDepth(t.task_id, new Set()));

  // Group by depth
  const layers: Record<number, string[]> = {};
  for (const [id, depth] of Object.entries(depths)) {
    (layers[depth] ??= []).push(id);
  }

  const NODE_W = 180;
  const NODE_H = 60;
  const H_GAP = 60;
  const V_GAP = 100;

  const nodes: Node[] = [];
  for (const [depthStr, ids] of Object.entries(layers)) {
    const depth = Number(depthStr);
    const totalWidth = ids.length * NODE_W + (ids.length - 1) * H_GAP;
    const startX = -totalWidth / 2;
    ids.forEach((id, i) => {
      nodes.push({
        id,
        position: { x: startX + i * (NODE_W + H_GAP), y: depth * (NODE_H + V_GAP) },
        data: { label: id },
        style: { width: NODE_W },
      });
    });
  }
  return nodes;
}

export default function DAGVisualization({ tasks, taskInstances }: Props) {
  const tiMap = useMemo(() => {
    const m: Record<string, TaskInstance> = {};
    taskInstances?.forEach((ti) => {
      // Keep the latest attempt
      if (!m[ti.task_id] || ti.attempt_number > m[ti.task_id].attempt_number) {
        m[ti.task_id] = ti;
      }
    });
    return m;
  }, [taskInstances]);

  const initialNodes = useMemo(() => {
    const nodes = layoutNodes(tasks);
    return nodes.map((n) => {
      const ti = tiMap[n.id];
      const stateClass = ti ? getStateColor(ti.state) : "bg-white";
      return {
        ...n,
        data: {
          label: (
            <div className={`px-3 py-2 rounded-lg border ${stateClass}`}>
              <div className="font-medium text-sm">{n.id}</div>
              {ti && (
                <div className="text-xs mt-1 opacity-75">{ti.state}</div>
              )}
            </div>
          ),
        },
        style: { ...n.style, background: "transparent", border: "none", padding: 0 },
      };
    });
  }, [tasks, tiMap]);

  const initialEdges = useMemo(() => {
    const edges: Edge[] = [];
    tasks.forEach((t) => {
      t.depends_on.forEach((dep) => {
        edges.push({
          id: `${dep}->${t.task_id}`,
          source: dep,
          target: t.task_id,
          animated: !!tiMap[dep] && tiMap[dep].state === "running",
          style: { stroke: "#6b7280", strokeWidth: 2 },
        });
      });
    });
    return edges;
  }, [tasks, tiMap]);

  const [nodes, , onNodesChange] = useNodesState(initialNodes);
  const [edges, , onEdgesChange] = useEdgesState(initialEdges);

  return (
    <div className="w-full h-[500px] bg-white rounded-lg border border-gray-200">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        fitView
        attributionPosition="bottom-left"
      >
        <Background />
        <Controls />
        <MiniMap />
      </ReactFlow>
    </div>
  );
}
