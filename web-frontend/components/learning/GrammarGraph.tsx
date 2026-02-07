import { useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { ConceptGraph, ConceptGraphNode } from '@/types/grammar';

interface GrammarGraphProps {
  graph: ConceptGraph;
  onConceptClick?: (conceptId: number) => void;
  selectedLevel?: string | null;
}

// SVG uses fill-* for backgrounds and stroke-* for borders
const stateColors: Record<string, string> = {
  neu: 'fill-gray-200 stroke-gray-400',
  'ausbaufähig': 'fill-orange-200 stroke-orange-400',
  in_arbeit: 'fill-yellow-200 stroke-yellow-400',
  gefestigt: 'fill-blue-200 stroke-blue-400',
  gemeistert: 'fill-green-200 stroke-green-400',
};

// HTML legend uses bg-* and border-*
const legendColors: Record<string, string> = {
  neu: 'bg-gray-200 border-gray-400',
  'ausbaufähig': 'bg-orange-200 border-orange-400',
  in_arbeit: 'bg-yellow-200 border-yellow-400',
  gefestigt: 'bg-blue-200 border-blue-400',
  gemeistert: 'bg-green-200 border-green-400',
};

// SVG uses fill-* for backgrounds
const levelColors: Record<string, string> = {
  A1: 'fill-green-500',
  A2: 'fill-green-600',
  B1: 'fill-yellow-500',
  B2: 'fill-orange-500',
  C1: 'fill-red-500',
  C2: 'fill-purple-500',
};

export default function GrammarGraph({
  graph,
  onConceptClick,
  selectedLevel,
}: GrammarGraphProps) {
  const [hoveredNode, setHoveredNode] = useState<number | null>(null);
  const [selectedNode, setSelectedNode] = useState<ConceptGraphNode | null>(null);

  // Filter nodes by level if selected
  const filteredNodes = useMemo(() => {
    if (!selectedLevel) return graph.nodes;
    return graph.nodes.filter(n => n.level === selectedLevel);
  }, [graph.nodes, selectedLevel]);

  // Filter edges to only show edges between visible nodes
  const filteredEdges = useMemo(() => {
    const nodeIds = new Set(filteredNodes.map(n => n.id));
    return graph.edges.filter(e => nodeIds.has(e.source) && nodeIds.has(e.target));
  }, [graph.edges, filteredNodes]);

  // Group nodes by level for layout
  const levelGroups = useMemo(() => {
    const groups: Record<string, ConceptGraphNode[]> = {};
    const levels = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'];

    for (const level of levels) {
      groups[level] = filteredNodes.filter(n => n.level === level);
    }

    return groups;
  }, [filteredNodes]);

  // Calculate node positions
  const nodePositions = useMemo(() => {
    const positions: Record<number, { x: number; y: number }> = {};
    const levels = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'];
    const levelWidth = 180;
    const nodeHeight = 80;
    const startX = 20;
    const startY = 60;

    levels.forEach((level, levelIndex) => {
      const nodesInLevel = levelGroups[level] || [];
      nodesInLevel.forEach((node, nodeIndex) => {
        positions[node.id] = {
          x: startX + levelIndex * levelWidth,
          y: startY + nodeIndex * nodeHeight,
        };
      });
    });

    return positions;
  }, [levelGroups]);

  // Calculate SVG dimensions
  const svgHeight = useMemo(() => {
    const maxNodes = Math.max(
      ...Object.values(levelGroups).map(nodes => nodes.length),
      1
    );
    return 60 + maxNodes * 80 + 40;
  }, [levelGroups]);

  const handleNodeClick = (node: ConceptGraphNode) => {
    setSelectedNode(selectedNode?.id === node.id ? null : node);
    if (onConceptClick && !node.is_locked) {
      onConceptClick(node.id);
    }
  };

  return (
    <div className="space-y-4">
      {/* Legend */}
      <div className="flex flex-wrap gap-4 text-sm">
        <span className="text-gray-600 dark:text-gray-400">Status:</span>
        {Object.entries({
          neu: 'Neu',
          'ausbaufähig': 'Ausbaufähig',
          in_arbeit: 'In Arbeit',
          gefestigt: 'Gefestigt',
          gemeistert: 'Gemeistert',
        }).map(([state, label]) => (
          <div key={state} className="flex items-center gap-1">
            <div className={`w-3 h-3 rounded border ${legendColors[state]}`} />
            <span className="text-gray-600 dark:text-gray-300">{label}</span>
          </div>
        ))}
      </div>

      {/* Graph Container */}
      <div className="overflow-x-auto bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
        <svg
          width="1100"
          height={svgHeight}
          className="min-w-[1100px]"
        >
          {/* Level Headers */}
          {['A1', 'A2', 'B1', 'B2', 'C1', 'C2'].map((level, i) => (
            <g key={level}>
              <rect
                x={20 + i * 180}
                y={10}
                width={160}
                height={30}
                rx={6}
                className={`${levelColors[level]}`}
              />
              <text
                x={100 + i * 180}
                y={30}
                textAnchor="middle"
                className="fill-white font-bold text-sm"
              >
                {level}
              </text>
            </g>
          ))}

          {/* Edges (prerequisite lines) */}
          {filteredEdges.map((edge, i) => {
            const sourcePos = nodePositions[edge.source];
            const targetPos = nodePositions[edge.target];
            if (!sourcePos || !targetPos) return null;

            const isHighlighted =
              hoveredNode === edge.source || hoveredNode === edge.target;

            return (
              <motion.path
                key={`edge-${i}`}
                d={`M ${sourcePos.x + 140} ${sourcePos.y + 25}
                    C ${sourcePos.x + 160} ${sourcePos.y + 25},
                      ${targetPos.x - 20} ${targetPos.y + 25},
                      ${targetPos.x} ${targetPos.y + 25}`}
                fill="none"
                stroke={isHighlighted ? '#3B82F6' : '#CBD5E1'}
                strokeWidth={isHighlighted ? 2 : 1}
                strokeDasharray={isHighlighted ? '' : '4 2'}
                initial={{ pathLength: 0 }}
                animate={{ pathLength: 1 }}
                transition={{ duration: 0.5, delay: i * 0.02 }}
              />
            );
          })}

          {/* Nodes */}
          {filteredNodes.map((node, i) => {
            const pos = nodePositions[node.id];
            if (!pos) return null;

            const isHovered = hoveredNode === node.id;
            const isSelected = selectedNode?.id === node.id;

            return (
              <motion.g
                key={node.id}
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: i * 0.03 }}
                onMouseEnter={() => setHoveredNode(node.id)}
                onMouseLeave={() => setHoveredNode(null)}
                onClick={() => handleNodeClick(node)}
                style={{ cursor: node.is_locked ? 'not-allowed' : 'pointer' }}
              >
                {/* Node Background */}
                <rect
                  x={pos.x}
                  y={pos.y}
                  width={160}
                  height={50}
                  rx={8}
                  strokeWidth={isSelected ? 2 : 1.5}
                  className={`${stateColors[node.state]} ${
                    node.is_locked ? 'opacity-50' : ''
                  } ${isSelected ? 'stroke-blue-500' : ''}`}
                  style={{
                    filter: isHovered && !node.is_locked ? 'brightness(0.95)' : '',
                  }}
                />

                {/* Lock icon for locked concepts */}
                {node.is_locked && (
                  <text
                    x={pos.x + 140}
                    y={pos.y + 20}
                    className="fill-gray-400 text-sm"
                  >
                    🔒
                  </text>
                )}

                {/* Node Name */}
                <text
                  x={pos.x + 10}
                  y={pos.y + 22}
                  className={`text-xs font-medium ${
                    node.is_locked ? 'fill-gray-400' : 'fill-gray-800 dark:fill-gray-200'
                  }`}
                >
                  {node.name.length > 22 ? node.name.slice(0, 20) + '...' : node.name}
                </text>

                {/* Score/Progress indicator */}
                {!node.is_locked && node.reps > 0 && (
                  <g>
                    <rect
                      x={pos.x + 10}
                      y={pos.y + 32}
                      width={100}
                      height={6}
                      rx={3}
                      className="fill-gray-200 dark:fill-gray-600"
                    />
                    <rect
                      x={pos.x + 10}
                      y={pos.y + 32}
                      width={Math.min(100, node.score * 10)}
                      height={6}
                      rx={3}
                      className={
                        node.score >= 7
                          ? 'fill-green-500'
                          : node.score >= 5
                          ? 'fill-yellow-500'
                          : 'fill-orange-500'
                      }
                    />
                    <text
                      x={pos.x + 120}
                      y={pos.y + 38}
                      className="fill-gray-500 text-xs"
                    >
                      {node.score.toFixed(1)}
                    </text>
                  </g>
                )}
              </motion.g>
            );
          })}
        </svg>
      </div>

      {/* Selected Node Details */}
      {selectedNode && (
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4"
        >
          <div className="flex items-start justify-between">
            <div>
              <h4 className="font-semibold text-gray-900 dark:text-white">
                {selectedNode.name}
              </h4>
              <div className="flex items-center gap-2 mt-1">
                <span className={`px-2 py-0.5 rounded text-xs ${levelColors[selectedNode.level]} text-white`}>
                  {selectedNode.level}
                </span>
                {selectedNode.category && (
                  <span className="text-xs text-gray-500 dark:text-gray-400">
                    {selectedNode.category}
                  </span>
                )}
              </div>
            </div>
            <button
              onClick={() => setSelectedNode(null)}
              className="text-gray-400 hover:text-gray-600"
            >
              ✕
            </button>
          </div>

          {selectedNode.description && (
            <p className="text-sm text-gray-600 dark:text-gray-300 mt-3">
              {selectedNode.description}
            </p>
          )}

          <div className="flex items-center gap-4 mt-3 text-sm">
            <span className="text-gray-500">
              Status: <span className="font-medium">{getStateLabel(selectedNode.state)}</span>
            </span>
            {selectedNode.reps > 0 && (
              <>
                <span className="text-gray-500">
                  Score: <span className="font-medium">{selectedNode.score.toFixed(1)}/10</span>
                </span>
                <span className="text-gray-500">
                  Wiederholungen: <span className="font-medium">{selectedNode.reps}</span>
                </span>
              </>
            )}
          </div>

          {selectedNode.prerequisites.length > 0 && (
            <div className="mt-3">
              <span className="text-xs text-gray-500">Voraussetzungen:</span>
              <div className="flex flex-wrap gap-1 mt-1">
                {selectedNode.prerequisites.map(prereqId => {
                  const prereq = graph.nodes.find(n => n.id === prereqId);
                  return prereq ? (
                    <span
                      key={prereqId}
                      className="px-2 py-0.5 bg-gray-100 dark:bg-gray-700 rounded text-xs text-gray-600 dark:text-gray-300"
                    >
                      {prereq.name}
                    </span>
                  ) : null;
                })}
              </div>
            </div>
          )}

          {!selectedNode.is_locked && onConceptClick && (
            <button
              onClick={() => onConceptClick(selectedNode.id)}
              className="mt-4 px-4 py-2 bg-blue-500 text-white rounded-lg text-sm font-medium hover:bg-blue-600 transition-colors"
            >
              Übung starten
            </button>
          )}
        </motion.div>
      )}
    </div>
  );
}

function getStateLabel(state: string): string {
  const labels: Record<string, string> = {
    neu: 'Neu',
    'ausbaufähig': 'Ausbaufähig',
    in_arbeit: 'In Arbeit',
    gefestigt: 'Gefestigt',
    gemeistert: 'Gemeistert',
  };
  return labels[state] || state;
}
