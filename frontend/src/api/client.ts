import axios from 'axios';
import type { Document, SearchResult, UploadResponse, GraphData, EntityDetail, Collection, CollectionStats, Tag } from '../types';

const API_BASE_URL = '/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const uploadDocument = async (file: File, collection?: string, tags?: string): Promise<UploadResponse> => {
  const formData = new FormData();
  formData.append('file', file);
  if (collection) {
    formData.append('collection', collection);
  }
  if (tags) {
    formData.append('tags', tags);
  }

  const response = await api.post<UploadResponse>('/ingest/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });

  return response.data;
};

export const getDocuments = async (collection?: string): Promise<Document[]> => {
  const response = await api.get<Document[]>('/ingest/documents', {
    params: collection ? { collection } : {},
  });
  return response.data;
};

export const deleteDocument = async (documentId: string): Promise<void> => {
  await api.delete(`/ingest/documents/${documentId}`);
};

export const searchDocuments = async (
  query: string,
  limit: number = 10,
  collection?: string,
  tags?: string
): Promise<SearchResult[]> => {
  const response = await api.get<SearchResult[]>('/search', {
    params: { query, limit, collection, tags },
  });
  return response.data;
};

export const getGraphData = async (
  limit?: number,
  entityType?: string,
  minMentions?: number,
  collection?: string,
  tags?: string
): Promise<GraphData> => {
  const response = await api.get<GraphData>('/graph/full', {
    params: {
      limit,
      entity_type: entityType,
      min_mentions: minMentions,
      collection,
      tags,
    },
  });
  return response.data;
};

export const getEntityDetail = async (entityId: string): Promise<EntityDetail> => {
  const response = await api.get<EntityDetail>(`/graph/entity/${entityId}`);
  return response.data;
};

// Collection management
export const getCollections = async (): Promise<Collection[]> => {
  const response = await api.get<Collection[]>('/collections');
  return response.data;
};

export const createCollection = async (name: string): Promise<Collection> => {
  const response = await api.post<Collection>('/collections', { name });
  return response.data;
};

export const deleteCollection = async (name: string): Promise<void> => {
  await api.delete(`/collections/${name}`);
};

export const getCollectionStats = async (name: string): Promise<CollectionStats> => {
  const response = await api.get<CollectionStats>(`/collections/${name}/stats`);
  return response.data;
};

// Tag management
export const getTags = async (collection?: string): Promise<Tag[]> => {
  const response = await api.get<Tag[]>('/tags', {
    params: collection ? { collection } : {},
  });
  return response.data;
};

export const getDocumentTags = async (documentId: number): Promise<{ document_id: number; tags: string[] }> => {
  const response = await api.get<{ document_id: number; tags: string[] }>(`/tags/documents/${documentId}/tags`);
  return response.data;
};

export const updateDocumentTags = async (documentId: number, tags: string[]): Promise<{ status: string; document_id: number; tags: string[] }> => {
  const response = await api.put<{ status: string; document_id: number; tags: string[] }>(`/tags/documents/${documentId}/tags`, { tags });
  return response.data;
};

export default api;
