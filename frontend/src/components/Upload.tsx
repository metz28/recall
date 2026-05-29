import { useState, useRef, DragEvent, ChangeEvent } from 'react';
import { uploadDocument, getDocuments, createCollection } from '../api/client';
import { useCollections } from '../contexts/CollectionContext';
import { useTags } from '../contexts/TagContext';
import CollectionSelector from './CollectionSelector';
import TagInput from './TagInput';
import type { Document } from '../types';

const Upload = () => {
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [showDocuments, setShowDocuments] = useState(false);
  const [selectedCollection, setSelectedCollection] = useState<string>('default');
  const [showNewCollection, setShowNewCollection] = useState(false);
  const [newCollectionName, setNewCollectionName] = useState('');
  const [documentTags, setDocumentTags] = useState<string[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { activeCollection, refreshCollections } = useCollections();
  const { refreshTags } = useTags();

  const handleDragEnter = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = async (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const files = e.dataTransfer.files;
    if (files.length > 0) {
      await handleUpload(files[0]);
    }
  };

  const handleFileInput = async (e: ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      await handleUpload(files[0]);
    }
  };

  const handleUpload = async (file: File) => {
    setUploading(true);
    setMessage(null);

    try {
      const tagsString = documentTags.join(',');
      const response = await uploadDocument(file, selectedCollection, tagsString);
      setMessage({
        type: 'success',
        text: `Successfully uploaded "${response.title}" to "${selectedCollection}" (${response.num_chunks} chunks)`,
      });

      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }

      // Clear tags after successful upload
      setDocumentTags([]);

      await refreshCollections();
      await refreshTags();

      if (showDocuments) {
        await loadDocuments();
      }
    } catch (error: any) {
      setMessage({
        type: 'error',
        text: error.response?.data?.detail || 'Failed to upload document',
      });
    } finally {
      setUploading(false);
    }
  };

  const handleCreateCollection = async () => {
    if (!newCollectionName.trim()) {
      setMessage({
        type: 'error',
        text: 'Collection name cannot be empty',
      });
      return;
    }

    try {
      await createCollection(newCollectionName);
      await refreshCollections();
      setSelectedCollection(newCollectionName.toLowerCase());
      setNewCollectionName('');
      setShowNewCollection(false);
      setMessage({
        type: 'success',
        text: `Collection "${newCollectionName}" created successfully`,
      });
    } catch (error: any) {
      setMessage({
        type: 'error',
        text: error.response?.data?.detail || 'Failed to create collection',
      });
    }
  };

  const loadDocuments = async () => {
    try {
      const docs = await getDocuments(activeCollection || undefined);
      setDocuments(docs);
      setShowDocuments(true);
    } catch (error: any) {
      setMessage({
        type: 'error',
        text: error.response?.data?.detail || 'Failed to load documents',
      });
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(2) + ' MB';
  };

  const formatDate = (dateString: string): string => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="max-w-4xl mx-auto p-6">
      <h1 className="text-3xl font-bold mb-8 text-gray-800">Upload Documents</h1>

      <div className="mb-6 space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Upload to Collection
          </label>
          <div className="flex gap-2">
            <div className="flex-1">
              <CollectionSelector
                showAllOption={false}
                onChange={(collection) => setSelectedCollection(collection || 'default')}
              />
            </div>
            <button
              onClick={() => setShowNewCollection(!showNewCollection)}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
            >
              {showNewCollection ? 'Cancel' : 'New Collection'}
            </button>
          </div>
        </div>

        {showNewCollection && (
          <div className="flex gap-2">
            <input
              type="text"
              value={newCollectionName}
              onChange={(e) => setNewCollectionName(e.target.value)}
              placeholder="Enter collection name (lowercase, alphanumeric)"
              className="flex-1 px-3 py-2 border rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
              onKeyPress={(e) => {
                if (e.key === 'Enter') {
                  handleCreateCollection();
                }
              }}
            />
            <button
              onClick={handleCreateCollection}
              className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 transition-colors"
            >
              Create
            </button>
          </div>
        )}

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Tags (optional)
          </label>
          <TagInput
            value={documentTags}
            onChange={setDocumentTags}
            placeholder="Add tags (comma-separated)"
          />
        </div>
      </div>

      <div
        className={`border-2 border-dashed rounded-lg p-12 text-center transition-colors ${
          isDragging
            ? 'border-blue-500 bg-blue-50'
            : 'border-gray-300 hover:border-gray-400'
        }`}
        onDragEnter={handleDragEnter}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          accept=".txt,.pdf,.docx,.md,.html"
          onChange={handleFileInput}
          disabled={uploading}
        />

        <div className="space-y-4">
          <svg
            className="mx-auto h-12 w-12 text-gray-400"
            stroke="currentColor"
            fill="none"
            viewBox="0 0 48 48"
            aria-hidden="true"
          >
            <path
              d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>

          <div className="text-gray-600">
            <button
              type="button"
              className="text-blue-600 hover:text-blue-700 font-medium"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
            >
              Click to upload
            </button>
            <span> or drag and drop</span>
          </div>

          <p className="text-sm text-gray-500">
            PDF, DOCX, TXT, Markdown, or HTML (max 50MB)
          </p>
        </div>

        {uploading && (
          <div className="mt-4">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            <p className="mt-2 text-sm text-gray-600">Uploading and processing...</p>
          </div>
        )}
      </div>

      {message && (
        <div
          className={`mt-4 p-4 rounded-lg ${
            message.type === 'success'
              ? 'bg-green-50 text-green-800 border border-green-200'
              : 'bg-red-50 text-red-800 border border-red-200'
          }`}
        >
          {message.text}
        </div>
      )}

      <div className="mt-8">
        <button
          onClick={loadDocuments}
          className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors"
        >
          {showDocuments ? 'Refresh Documents' : 'View All Documents'}
        </button>

        {showDocuments && (
          <div className="mt-4">
            <h2 className="text-xl font-semibold mb-4 text-gray-800">
              Uploaded Documents ({documents.length})
            </h2>

            {documents.length === 0 ? (
              <p className="text-gray-500">No documents uploaded yet.</p>
            ) : (
              <div className="space-y-3">
                {documents.map((doc) => (
                  <div
                    key={doc.id}
                    className="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow"
                  >
                    <div className="flex justify-between items-start">
                      <div className="flex-1">
                        <h3 className="font-medium text-gray-900">{doc.title}</h3>
                        <div className="mt-1 text-sm text-gray-500 space-x-4">
                          <span>{doc.file_type.toUpperCase()}</span>
                          <span>{formatFileSize(doc.file_size)}</span>
                          <span>{doc.num_chunks} chunks</span>
                          {doc.collection && (
                            <span className="text-blue-600">📁 {doc.collection}</span>
                          )}
                        </div>
                        {doc.tags && doc.tags.length > 0 && (
                          <div className="mt-2 flex flex-wrap gap-1">
                            {doc.tags.map((tag) => (
                              <span
                                key={tag}
                                className="px-2 py-1 bg-purple-100 text-purple-700 text-xs rounded-full"
                              >
                                {tag}
                              </span>
                            ))}
                          </div>
                        )}
                        <p className="mt-1 text-xs text-gray-400">
                          Uploaded {formatDate(doc.created_at)}
                        </p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default Upload;
