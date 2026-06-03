import React, { useEffect, useState } from 'react';
import { listShares, revokeShare, deleteShare } from '../api/client';
import type { ShareResponse } from '../types';

const ShareManager: React.FC = () => {
  const [shares, setShares] = useState<ShareResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadShares();
  }, []);

  const loadShares = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await listShares();
      setShares(response.shares);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load shares');
    } finally {
      setIsLoading(false);
    }
  };

  const handleRevoke = async (shareId: string) => {
    if (!confirm('Are you sure you want to revoke this share link? It will no longer be accessible.')) {
      return;
    }

    try {
      await revokeShare(shareId);
      await loadShares();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to revoke share');
    }
  };

  const handleDelete = async (shareId: string) => {
    if (!confirm('Are you sure you want to permanently delete this share link? This action cannot be undone.')) {
      return;
    }

    try {
      await deleteShare(shareId);
      await loadShares();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to delete share');
    }
  };

  const handleCopyUrl = (url: string) => {
    navigator.clipboard.writeText(url);
    alert('Share URL copied to clipboard!');
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <p className="text-red-800">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold">Shared Links</h2>
        <button
          onClick={loadShares}
          className="px-4 py-2 text-sm bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
        >
          Refresh
        </button>
      </div>

      {shares.length === 0 ? (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-8 text-center">
          <svg className="w-16 h-16 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
          </svg>
          <p className="text-gray-600">No shared links yet</p>
          <p className="text-sm text-gray-500 mt-2">
            Share documents, searches, or collections to see them here
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {shares.map((share) => (
            <div
              key={share.id}
              className={`bg-white border rounded-lg p-4 ${
                !share.is_active ? 'opacity-60 bg-gray-50' : ''
              }`}
            >
              <div className="flex justify-between items-start">
                <div className="flex-1">
                  <div className="flex items-center space-x-2 mb-2">
                    <span className={`inline-block px-2 py-1 text-xs rounded ${
                      share.resource_type === 'document' ? 'bg-blue-100 text-blue-800' :
                      share.resource_type === 'search' ? 'bg-green-100 text-green-800' :
                      'bg-purple-100 text-purple-800'
                    }`}>
                      {share.resource_type}
                    </span>
                    {!share.is_active && (
                      <span className="inline-block px-2 py-1 text-xs bg-red-100 text-red-800 rounded">
                        Revoked
                      </span>
                    )}
                    {share.expires_at && new Date(share.expires_at) < new Date() && (
                      <span className="inline-block px-2 py-1 text-xs bg-orange-100 text-orange-800 rounded">
                        Expired
                      </span>
                    )}
                  </div>

                  <div className="text-sm text-gray-600 space-y-1">
                    <p>
                      <strong>Created:</strong> {new Date(share.created_at).toLocaleString()}
                    </p>
                    {share.expires_at && (
                      <p>
                        <strong>Expires:</strong> {new Date(share.expires_at).toLocaleString()}
                      </p>
                    )}
                    <p>
                      <strong>Views:</strong> {share.view_count}
                      {share.last_accessed && ` (Last: ${new Date(share.last_accessed).toLocaleString()})`}
                    </p>
                    {share.metadata?.query && (
                      <p>
                        <strong>Query:</strong> "{share.metadata.query}"
                      </p>
                    )}
                    {share.resource_type === 'collection' && share.resource_id && (
                      <p>
                        <strong>Collection:</strong> {share.resource_id}
                      </p>
                    )}
                  </div>

                  <div className="flex items-center space-x-2 mt-3">
                    <input
                      type="text"
                      value={share.share_url}
                      readOnly
                      className="flex-1 px-2 py-1 text-sm border border-gray-300 rounded bg-gray-50 font-mono"
                    />
                    <button
                      onClick={() => handleCopyUrl(share.share_url)}
                      className="px-3 py-1 text-sm bg-blue-500 text-white rounded hover:bg-blue-600"
                    >
                      Copy
                    </button>
                  </div>
                </div>

                <div className="flex flex-col space-y-2 ml-4">
                  {share.is_active && (
                    <button
                      onClick={() => handleRevoke(share.id)}
                      className="px-3 py-1 text-sm bg-yellow-500 text-white rounded hover:bg-yellow-600"
                      title="Revoke this share link"
                    >
                      Revoke
                    </button>
                  )}
                  <button
                    onClick={() => handleDelete(share.id)}
                    className="px-3 py-1 text-sm bg-red-500 text-white rounded hover:bg-red-600"
                    title="Permanently delete this share"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default ShareManager;
