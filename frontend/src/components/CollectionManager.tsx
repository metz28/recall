import { useState, useEffect } from 'react';
import { useCollections } from '../contexts/CollectionContext';
import { getCollectionStats, deleteCollection } from '../api/client';
import type { CollectionStats } from '../types';

const CollectionManager = () => {
  const { collections, activeCollection, setActiveCollection, refreshCollections } = useCollections();
  const [selectedCollection, setSelectedCollection] = useState<string | null>(null);
  const [stats, setStats] = useState<CollectionStats | null>(null);
  const [loadingStats, setLoadingStats] = useState(false);
  const [deletingCollection, setDeletingCollection] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (selectedCollection) {
      loadStats(selectedCollection);
    }
  }, [selectedCollection]);

  const loadStats = async (collectionName: string) => {
    try {
      setLoadingStats(true);
      setError(null);
      const data = await getCollectionStats(collectionName);
      setStats(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load collection stats');
      setStats(null);
    } finally {
      setLoadingStats(false);
    }
  };

  const handleDelete = async (collectionName: string) => {
    if (collectionName === 'default') {
      setError('Cannot delete the default collection');
      return;
    }

    const confirmed = window.confirm(
      `Are you sure you want to delete collection "${collectionName}"? This will delete all documents, chunks, and entities in this collection. This action cannot be undone.`
    );

    if (!confirmed) return;

    try {
      setDeletingCollection(collectionName);
      setError(null);
      await deleteCollection(collectionName);
      await refreshCollections();

      if (activeCollection === collectionName) {
        setActiveCollection(null);
      }

      if (selectedCollection === collectionName) {
        setSelectedCollection(null);
        setStats(null);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to delete collection');
    } finally {
      setDeletingCollection(null);
    }
  };

  const handleSwitch = (collectionName: string) => {
    setActiveCollection(collectionName);
  };

  const formatDate = (dateString: string | null): string => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="max-w-6xl mx-auto p-6">
      <h1 className="text-3xl font-bold mb-8 text-gray-800">Collection Manager</h1>

      {error && (
        <div className="mb-6 bg-red-50 text-red-800 border border-red-200 rounded-lg p-4">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Collections List */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4 text-gray-800">Collections</h2>

          {collections.length === 0 ? (
            <p className="text-gray-500">No collections found.</p>
          ) : (
            <div className="space-y-3">
              {collections.map((collection) => (
                <div
                  key={collection.name}
                  className={`border rounded-lg p-4 transition-all ${
                    selectedCollection === collection.name
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <h3 className="font-medium text-gray-900">{collection.name}</h3>
                        {activeCollection === collection.name && (
                          <span className="px-2 py-1 bg-green-100 text-green-800 text-xs rounded">
                            Active
                          </span>
                        )}
                        {collection.name === 'default' && (
                          <span className="px-2 py-1 bg-gray-100 text-gray-800 text-xs rounded">
                            Default
                          </span>
                        )}
                      </div>
                      <div className="mt-2 text-sm text-gray-600">
                        <span>{collection.document_count} documents</span>
                        <span className="mx-2">•</span>
                        <span>{collection.total_chunks} chunks</span>
                      </div>
                    </div>
                  </div>

                  <div className="mt-3 flex gap-2">
                    <button
                      onClick={() => setSelectedCollection(collection.name)}
                      className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
                    >
                      View Details
                    </button>
                    <button
                      onClick={() => handleSwitch(collection.name)}
                      disabled={activeCollection === collection.name}
                      className="px-3 py-1 text-sm bg-gray-600 text-white rounded hover:bg-gray-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
                    >
                      {activeCollection === collection.name ? 'Current' : 'Switch To'}
                    </button>
                    {collection.name !== 'default' && (
                      <button
                        onClick={() => handleDelete(collection.name)}
                        disabled={deletingCollection === collection.name}
                        className="px-3 py-1 text-sm bg-red-600 text-white rounded hover:bg-red-700 disabled:bg-red-400 disabled:cursor-not-allowed transition-colors"
                      >
                        {deletingCollection === collection.name ? 'Deleting...' : 'Delete'}
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Collection Details */}
        <div className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4 text-gray-800">Collection Details</h2>

          {!selectedCollection ? (
            <div className="text-center py-12 text-gray-500">
              Select a collection to view details
            </div>
          ) : loadingStats ? (
            <div className="text-center py-12">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
              <p className="mt-2 text-gray-600">Loading stats...</p>
            </div>
          ) : stats ? (
            <div className="space-y-4">
              <div>
                <h3 className="text-2xl font-bold text-gray-900">{stats.collection}</h3>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="bg-blue-50 rounded-lg p-4">
                  <p className="text-sm text-blue-600 font-medium">Documents</p>
                  <p className="text-2xl font-bold text-blue-900">{stats.document_count}</p>
                </div>

                <div className="bg-green-50 rounded-lg p-4">
                  <p className="text-sm text-green-600 font-medium">Chunks</p>
                  <p className="text-2xl font-bold text-green-900">{stats.total_chunks}</p>
                </div>

                <div className="bg-purple-50 rounded-lg p-4">
                  <p className="text-sm text-purple-600 font-medium">Entities</p>
                  <p className="text-2xl font-bold text-purple-900">{stats.entity_count}</p>
                </div>

                <div className="bg-gray-50 rounded-lg p-4">
                  <p className="text-sm text-gray-600 font-medium">Avg Chunks/Doc</p>
                  <p className="text-2xl font-bold text-gray-900">
                    {stats.document_count > 0
                      ? (stats.total_chunks / stats.document_count).toFixed(1)
                      : '0'}
                  </p>
                </div>
              </div>

              <div className="pt-4 border-t space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Created:</span>
                  <span className="font-medium text-gray-900">{formatDate(stats.created_at)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Last Updated:</span>
                  <span className="font-medium text-gray-900">{formatDate(stats.updated_at)}</span>
                </div>
              </div>

              {stats.document_count === 0 && (
                <div className="mt-4 p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
                  <p className="text-sm text-yellow-800">
                    This collection is empty. Upload documents to this collection to populate it.
                  </p>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-12 text-red-500">Failed to load stats</div>
          )}
        </div>
      </div>
    </div>
  );
};

export default CollectionManager;
