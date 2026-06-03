import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import {
  getShareMetadata,
  getSharedDocument,
  getSharedDocumentChunks,
  getSharedSearch,
  getSharedCollection
} from '../api/client';
import type {
  ShareMetadata,
  SharedDocumentResponse,
  SharedSearchResponse,
  Document
} from '../types';

const SharedView: React.FC = () => {
  const { token } = useParams<{ token: string }>();
  const [metadata, setMetadata] = useState<ShareMetadata | null>(null);
  const [content, setContent] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;

    const loadSharedContent = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const meta = await getShareMetadata(token);
        setMetadata(meta);

        if (!meta.is_active) {
          setError('This share link has been revoked');
          return;
        }

        if (meta.is_expired) {
          setError('This share link has expired');
          return;
        }

        switch (meta.resource_type) {
          case 'document': {
            const doc = await getSharedDocument(token);
            const chunks = await getSharedDocumentChunks(token);
            setContent({ document: doc, chunks: chunks.chunks });
            break;
          }
          case 'search': {
            const searchResults = await getSharedSearch(token);
            setContent({ search: searchResults });
            break;
          }
          case 'collection': {
            const collection = await getSharedCollection(token);
            setContent({ collection });
            break;
          }
          default:
            setError('Unknown resource type');
        }
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Failed to load shared content');
      } finally {
        setIsLoading(false);
      }
    };

    loadSharedContent();
  }, [token]);

  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading shared content...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="max-w-md mx-4">
          <div className="bg-red-50 border border-red-200 rounded-lg p-6 text-center">
            <svg className="w-16 h-16 text-red-500 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <h2 className="text-xl font-bold text-red-800 mb-2">Unable to Load Content</h2>
            <p className="text-red-700">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 py-8">
      <div className="max-w-4xl mx-auto px-4">
        <div className="bg-white rounded-lg shadow-lg p-6 mb-6">
          <div className="border-b pb-4 mb-4">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-2xl font-bold text-gray-900">
                  {metadata?.resource_title || 'Shared Content'}
                </h1>
                <p className="text-sm text-gray-600 mt-1">
                  Shared by {metadata?.owner_username} on {new Date(metadata?.created_at || '').toLocaleDateString()}
                </p>
              </div>
              <div className="text-sm text-gray-500">
                <span className="inline-block px-3 py-1 bg-blue-100 text-blue-800 rounded-full">
                  {metadata?.resource_type}
                </span>
              </div>
            </div>
            {metadata?.expires_at && (
              <p className="text-sm text-gray-500 mt-2">
                Expires on {new Date(metadata.expires_at).toLocaleDateString()}
              </p>
            )}
          </div>

          {metadata?.resource_type === 'document' && content?.document && (
            <div>
              <div className="mb-4">
                <h2 className="text-xl font-semibold mb-2">{content.document.title}</h2>
                <div className="flex space-x-4 text-sm text-gray-600">
                  <span>Type: {content.document.file_type}</span>
                  <span>Chunks: {content.document.num_chunks}</span>
                  {content.document.tags && content.document.tags.length > 0 && (
                    <span>Tags: {content.document.tags.join(', ')}</span>
                  )}
                </div>
              </div>
              <div className="space-y-4">
                <h3 className="font-semibold text-lg">Document Content</h3>
                {content.chunks.map((chunk: any) => (
                  <div key={chunk.id} className="bg-gray-50 p-4 rounded border">
                    <p className="text-sm text-gray-800 whitespace-pre-wrap">{chunk.content}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {metadata?.resource_type === 'search' && content?.search && (
            <div>
              <div className="mb-4">
                <h2 className="text-xl font-semibold mb-2">Search Results</h2>
                <p className="text-gray-600">Query: "{content.search.query}"</p>
                <p className="text-sm text-gray-500 mt-1">
                  Found {content.search.total_results} results
                </p>
              </div>
              <div className="space-y-4">
                {content.search.results.map((result: any, idx: number) => (
                  <div key={idx} className="bg-gray-50 p-4 rounded border">
                    <div className="flex justify-between items-start mb-2">
                      <h3 className="font-semibold text-blue-600">{result.document_title}</h3>
                      <span className="text-xs text-gray-500 bg-gray-200 px-2 py-1 rounded">
                        Score: {(result.score * 100).toFixed(1)}%
                      </span>
                    </div>
                    <p className="text-sm text-gray-800 whitespace-pre-wrap">{result.content}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {metadata?.resource_type === 'collection' && content?.collection && (
            <div>
              <div className="mb-4">
                <h2 className="text-xl font-semibold mb-2">Collection: {content.collection.collection}</h2>
                <p className="text-sm text-gray-600">
                  {content.collection.total} documents
                </p>
              </div>
              <div className="space-y-3">
                {content.collection.documents.map((doc: Document) => (
                  <div key={doc.id} className="bg-gray-50 p-4 rounded border hover:bg-gray-100">
                    <h3 className="font-semibold text-gray-900">{doc.title}</h3>
                    <div className="flex space-x-4 text-sm text-gray-600 mt-1">
                      <span>Type: {doc.file_type}</span>
                      <span>Chunks: {doc.num_chunks}</span>
                      {doc.tags && doc.tags.length > 0 && (
                        <span>Tags: {doc.tags.join(', ')}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="text-center text-gray-600">
          <p className="text-sm">
            Powered by <a href="/" className="text-blue-600 hover:underline">Recall</a> - Personal Knowledge Base
          </p>
        </div>
      </div>
    </div>
  );
};

export default SharedView;
