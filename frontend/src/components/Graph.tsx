import { useState, useEffect, useMemo, useCallback } from 'react';
import {
  ReactFlow,
  Node,
  Edge,
  Controls,
  MiniMap,
  Background,
  useNodesState,
  useEdgesState,
  Panel,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { getGraphData, getEntityDetail } from '../api/client';
import { useCollections } from '../contexts/CollectionContext';
import CollectionSelector from './CollectionSelector';
import type { GraphData, EntityDetail } from '../types';

const ENTITY_TYPE_COLORS: Record<string, string> = {
  PERSON: '#3b82f6',      // blue-500
  ORG: '#8b5cf6',         // violet-500
  GPE: '#10b981',         // emerald-500
  PRODUCT: '#f59e0b',     // amber-500
  EVENT: '#ef4444',       // red-500
  WORK_OF_ART: '#ec4899', // pink-500
  LAW: '#6366f1',         // indigo-500
  NORP: '#14b8a6',        // teal-500
  FAC: '#f97316',         // orange-500
};

const RELATIONSHIP_TYPE_COLORS: Record<string, string> = {
  works_for: '#3b82f6',   // blue
  located_in: '#10b981',  // green
  created_by: '#8b5cf6',  // violet
  member_of: '#f59e0b',   // amber
  part_of: '#ec4899',     // pink
};

const DEFAULT_COLOR = '#6b7280'; // gray-500

interface NodeData extends Record<string, unknown> {
  label: string;
  type: string;
  mention_count: number;
  description?: string;
  variants?: string;
  id: string;
}

function Graph() {
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedEntityType, setSelectedEntityType] = useState<string>('');
  const [selectedEntity, setSelectedEntity] = useState<EntityDetail | null>(null);
  const [loadingEntity, setLoadingEntity] = useState(false);
  const { activeCollection } = useCollections();

  const [nodes, setNodes, onNodesChange] = useNodesState<Node<NodeData>>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);

  // Load graph data on mount and when collection changes
  useEffect(() => {
    const loadGraphData = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await getGraphData(100, undefined, undefined, activeCollection || undefined);
        setGraphData(data);
      } catch (err) {
        setError('Failed to load graph data. Please try again.');
      } finally {
        setLoading(false);
      }
    };

    loadGraphData();
  }, [activeCollection]);

  // Convert graph data to React Flow format
  useEffect(() => {
    if (!graphData) return;

    // Apply circular layout
    const radius = 300;
    const centerX = 400;
    const centerY = 300;

    const flowNodes: Node<NodeData>[] = graphData.nodes.map((node, index) => {
      const angle = (2 * Math.PI * index) / graphData.nodes.length;
      const x = centerX + radius * Math.cos(angle);
      const y = centerY + radius * Math.sin(angle);

      return {
        id: node.id,
        type: 'default',
        position: { x, y },
        data: {
          ...node,
        },
        style: {
          background: ENTITY_TYPE_COLORS[node.type] || DEFAULT_COLOR,
          color: '#ffffff',
          border: '2px solid #ffffff',
          borderRadius: '8px',
          padding: '10px',
          fontSize: '12px',
          fontWeight: 500,
          minWidth: '80px',
          textAlign: 'center',
        },
      };
    });

    const flowEdges: Edge[] = graphData.edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      type: 'smoothstep',
      animated: false,
      style: {
        stroke: RELATIONSHIP_TYPE_COLORS[edge.type] || DEFAULT_COLOR,
        strokeWidth: 2,
      },
      label: edge.type,
      labelStyle: {
        fontSize: 10,
        fill: '#6b7280',
      },
    }));

    setNodes(flowNodes);
    setEdges(flowEdges);
  }, [graphData, setNodes, setEdges]);

  // Filter nodes and edges based on search and entity type
  const filteredNodesAndEdges = useMemo(() => {
    if (!nodes.length) return { nodes: [], edges: [] };

    let filteredNodes = [...nodes];
    let filteredEdges = [...edges];

    // Filter by entity type
    if (selectedEntityType) {
      filteredNodes = filteredNodes.filter(
        (node) => node.data.type === selectedEntityType
      );

      const filteredNodeIds = new Set(filteredNodes.map((n) => n.id));
      filteredEdges = filteredEdges.filter(
        (edge) =>
          filteredNodeIds.has(edge.source) && filteredNodeIds.has(edge.target)
      );
    }

    // Apply search highlighting
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      filteredNodes = filteredNodes.map((node) => {
        const matches = node.data.label.toLowerCase().includes(query);
        return {
          ...node,
          style: {
            ...node.style,
            opacity: matches ? 1 : 0.3,
          },
        };
      });

      filteredEdges = filteredEdges.map((edge) => {
        const sourceNode = nodes.find((n) => n.id === edge.source);
        const targetNode = nodes.find((n) => n.id === edge.target);
        const sourceMatches = sourceNode?.data.label.toLowerCase().includes(query);
        const targetMatches = targetNode?.data.label.toLowerCase().includes(query);
        const matches = sourceMatches || targetMatches;

        return {
          ...edge,
          style: {
            ...edge.style,
            opacity: matches ? 1 : 0.3,
          },
        };
      });
    }

    return { nodes: filteredNodes, edges: filteredEdges };
  }, [nodes, edges, searchQuery, selectedEntityType]);

  // Handle node click
  const onNodeClick = useCallback(async (_event: React.MouseEvent, node: Node<NodeData>) => {
    try {
      setLoadingEntity(true);
      const entityData = await getEntityDetail(node.id);
      setSelectedEntity(entityData);
    } catch (err) {
      // Entity details loading failed silently
    } finally {
      setLoadingEntity(false);
    }
  }, []);

  // Get unique entity types for filter
  const entityTypes = useMemo(() => {
    if (!graphData) return [];
    return Object.keys(graphData.stats.entity_types).sort();
  }, [graphData]);

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-center h-96">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
            <p className="text-gray-600">Loading knowledge graph...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6">
          <div className="flex items-center">
            <svg
              className="h-6 w-6 text-red-600 mr-3"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <p className="text-red-800">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  if (!graphData || graphData.nodes.length === 0) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
          <div className="flex items-center">
            <svg
              className="h-6 w-6 text-yellow-600 mr-3"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <div>
              <p className="text-yellow-800 font-medium">No entities found</p>
              <p className="text-yellow-700 text-sm mt-1">
                Upload documents to start building your knowledge graph
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div className="bg-white rounded-lg shadow-sm p-6">
        {/* Controls Panel */}
        <div className="mb-4 flex flex-wrap gap-4">
          {/* Collection Filter */}
          <div className="flex-1 min-w-[200px]">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Collection
            </label>
            <CollectionSelector showAllOption={true} />
          </div>

          {/* Search */}
          <div className="flex-1 min-w-[250px]">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Search
            </label>
            <input
              type="text"
              placeholder="Search entities..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          {/* Entity Type Filter */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Entity Type
            </label>
            <select
              value={selectedEntityType}
              onChange={(e) => setSelectedEntityType(e.target.value)}
              className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="">All Types</option>
              {entityTypes.map((type) => (
                <option key={type} value={type}>
                  {type} ({graphData.stats.entity_types[type]})
                </option>
              ))}
            </select>
          </div>

          {/* Stats */}
          <div className="flex items-center space-x-4 px-4 py-2 bg-gray-50 rounded-lg text-sm">
            <div>
              <span className="font-medium text-gray-700">Nodes:</span>{' '}
              <span className="text-gray-900">{graphData.stats.total_nodes}</span>
            </div>
            <div>
              <span className="font-medium text-gray-700">Edges:</span>{' '}
              <span className="text-gray-900">{graphData.stats.total_edges}</span>
            </div>
          </div>
        </div>

        {/* Graph Visualization */}
        <div className="border border-gray-200 rounded-lg overflow-hidden" style={{ height: '600px' }}>
          <ReactFlow
            nodes={filteredNodesAndEdges.nodes}
            edges={filteredNodesAndEdges.edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={onNodeClick}
            fitView
            attributionPosition="bottom-left"
          >
            <Background />
            <Controls />
            <MiniMap
              nodeColor={(node) => node.style?.background as string || DEFAULT_COLOR}
              zoomable
              pannable
            />

            {/* Legend Panel */}
            <Panel position="top-right" className="bg-white p-4 rounded-lg shadow-lg">
              <h3 className="font-semibold text-gray-900 mb-2 text-sm">Entity Types</h3>
              <div className="space-y-1 text-xs">
                {Object.entries(ENTITY_TYPE_COLORS).map(([type, color]) => (
                  <div key={type} className="flex items-center space-x-2">
                    <div
                      className="w-3 h-3 rounded"
                      style={{ backgroundColor: color }}
                    ></div>
                    <span className="text-gray-700">{type}</span>
                  </div>
                ))}
              </div>
            </Panel>
          </ReactFlow>
        </div>

        {/* Entity Detail Sidebar */}
        {selectedEntity && (
          <div className="fixed right-0 top-0 bottom-0 w-96 bg-white shadow-2xl overflow-y-auto z-50">
            <div className="p-6">
              {/* Close button */}
              <button
                onClick={() => setSelectedEntity(null)}
                className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
              >
                <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>

              {/* Entity Header */}
              <div className="mb-6">
                <div className="flex items-center space-x-2 mb-2">
                  <div
                    className="w-4 h-4 rounded"
                    style={{
                      backgroundColor:
                        ENTITY_TYPE_COLORS[selectedEntity.entity_type] || DEFAULT_COLOR,
                    }}
                  ></div>
                  <span className="text-sm text-gray-500">{selectedEntity.entity_type}</span>
                </div>
                <h2 className="text-2xl font-bold text-gray-900">{selectedEntity.name}</h2>
                <p className="text-sm text-gray-600 mt-1">
                  {selectedEntity.mention_count} mention{selectedEntity.mention_count !== 1 ? 's' : ''}
                </p>
              </div>

              {/* Description */}
              {selectedEntity.description && (
                <div className="mb-6">
                  <h3 className="font-semibold text-gray-900 mb-2">Description</h3>
                  <p className="text-gray-700 text-sm">{selectedEntity.description}</p>
                </div>
              )}

              {/* Relationships */}
              {selectedEntity.relationships.length > 0 && (
                <div className="mb-6">
                  <h3 className="font-semibold text-gray-900 mb-2">
                    Relationships ({selectedEntity.relationships.length})
                  </h3>
                  <div className="space-y-2">
                    {selectedEntity.relationships.map((rel) => (
                      <div
                        key={rel.id}
                        className="p-3 bg-gray-50 rounded-lg text-sm"
                      >
                        <div className="flex items-center space-x-2 mb-1">
                          <span
                            className={`px-2 py-1 rounded text-xs font-medium ${
                              rel.direction === 'outgoing'
                                ? 'bg-blue-100 text-blue-800'
                                : 'bg-green-100 text-green-800'
                            }`}
                          >
                            {rel.direction}
                          </span>
                          <span className="font-medium text-gray-900">
                            {rel.relationship_type}
                          </span>
                        </div>
                        <p className="text-gray-700">
                          {rel.other_entity.name}{' '}
                          <span className="text-gray-500">({rel.other_entity.type})</span>
                        </p>
                        {rel.context && (
                          <p className="text-gray-600 text-xs mt-1 italic">
                            "{rel.context}"
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Sample Mentions */}
              {selectedEntity.sample_mentions.length > 0 && (
                <div>
                  <h3 className="font-semibold text-gray-900 mb-2">Sample Mentions</h3>
                  <div className="space-y-3">
                    {selectedEntity.sample_mentions.map((mention, index) => (
                      <div key={index} className="p-3 bg-gray-50 rounded-lg text-sm">
                        <p className="text-gray-700 mb-1">"{mention.context}"</p>
                        <p className="text-gray-500 text-xs">
                          from: {mention.document_title}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Loading overlay for entity details */}
        {loadingEntity && (
          <div className="fixed inset-0 bg-black bg-opacity-25 flex items-center justify-center z-40">
            <div className="bg-white rounded-lg p-6 shadow-xl">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
              <p className="text-gray-600 mt-3">Loading entity details...</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default Graph;
