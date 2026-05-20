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
