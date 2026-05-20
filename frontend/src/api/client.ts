import axios from 'axios';
import type { Document, SearchResult, UploadResponse } from '../types';

const API_BASE_URL = '/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const uploadDocument = async (file: File): Promise<UploadResponse> => {
  const formData = new FormData();
  formData.append('file', file);

  const response = await api.post<UploadResponse>('/ingest/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });

  return response.data;
};

export const getDocuments = async (): Promise<Document[]> => {
  const response = await api.get<Document[]>('/ingest/documents');
  return response.data;
};

export const deleteDocument = async (documentId: string): Promise<void> => {
  await api.delete(`/ingest/documents/${documentId}`);
};

export const searchDocuments = async (
  query: string,
  limit: number = 10
): Promise<SearchResult[]> => {
  const response = await api.get<SearchResult[]>('/search', {
    params: { query, limit },
  });
  return response.data;
};

export default api;
