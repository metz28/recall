export interface Document {
  id: string;
  title: string;
  source_type: string;
  source_path: string;
  file_type: string;
  file_size: number;
  num_chunks: number;
  created_at: string;
  updated_at: string;
  collection?: string;
  tags?: string[];
}

export interface SearchResult {
  chunk_id: string;
  document_id: string;
  document_title: string;
  content: string;
  score: number;
  chunk_index: number;
}

export interface UploadResponse {
  document_id: string;
  title: string;
  num_chunks: number;
  message: string;
}

export interface ErrorResponse {
  detail: string;
}

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  mention_count: number;
  description?: string;
  variants?: string;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: string;
  context?: string;
  confidence?: number;
}

export interface GraphStats {
  total_nodes: number;
  total_edges: number;
  entity_types: Record<string, number>;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  stats: GraphStats;
}

export interface EntityRelationship {
  id: string;
  relationship_type: string;
  direction: 'outgoing' | 'incoming';
  other_entity: {
    id: string;
    name: string;
    type: string;
  };
  context?: string;
  confidence?: number;
}

export interface EntityMention {
  context: string;
  document_title: string;
}

export interface EntityDetail {
  id: string;
  name: string;
  entity_type: string;
  description?: string;
  mention_count: number;
  variants?: string;
  created_at: string;
  relationships: EntityRelationship[];
  sample_mentions: EntityMention[];
}

export interface Collection {
  name: string;
  document_count: number;
  total_chunks: number;
}

export interface CollectionStats {
  collection: string;
  document_count: number;
  total_chunks: number;
  entity_count: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface Tag {
  tag: string;
  count: number;
}
