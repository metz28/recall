import { useState, FormEvent } from 'react';
import { searchDocuments } from '../api/client';
import { useCollections } from '../contexts/CollectionContext';
import { useTags } from '../contexts/TagContext';
import CollectionSelector from './CollectionSelector';
import TagSelector from './TagSelector';
import type { SearchResult } from '../types';

const Search = () => {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [limit, setLimit] = useState(10);
  const { activeCollection } = useCollections();
  const { selectedTags } = useTags();

  const handleSearch = async (e: FormEvent) => {
    e.preventDefault();

    if (!query.trim()) {
      return;
    }

    setSearching(true);
    setError(null);
    setHasSearched(true);

    try {
      const tagsString = selectedTags.length > 0 ? selectedTags.join(',') : undefined;
      const searchResults = await searchDocuments(query, limit, activeCollection || undefined, tagsString);
      setResults(searchResults);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to search documents');
      setResults([]);
    } finally {
      setSearching(false);
    }
  };

  const highlightQuery = (text: string, query: string): JSX.Element => {
    if (!query.trim()) return <>{text}</>;

    const parts = text.split(new RegExp(`(${query})`, 'gi'));
    return (
      <>
        {parts.map((part, index) =>
          part.toLowerCase() === query.toLowerCase() ? (
            <mark key={index} className="bg-yellow-200 px-1 rounded">
              {part}
            </mark>
          ) : (
            <span key={index}>{part}</span>
          )
        )}
      </>
    );
  };

  const formatScore = (score: number): string => {
    return (score * 100).toFixed(1) + '%';
  };

  return (
    <div className="max-w-4xl mx-auto p-6">
      <h1 className="text-3xl font-bold mb-8 text-gray-800">Search Knowledge Base</h1>

      <form onSubmit={handleSearch} className="mb-8">
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Search in Collection
          </label>
          <CollectionSelector showAllOption={true} />
        </div>

        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Filter by Tags
          </label>
          <TagSelector />
        </div>

        <div className="flex gap-4 mb-4">
          <div className="flex-1">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Enter your search query..."
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
              disabled={searching}
            />
          </div>

          <div className="w-32">
            <select
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value))}
              className="w-full px-3 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
              disabled={searching}
            >
              <option value={5}>Top 5</option>
              <option value={10}>Top 10</option>
              <option value={20}>Top 20</option>
              <option value={50}>Top 50</option>
            </select>
          </div>

          <button
            type="submit"
            disabled={searching || !query.trim()}
            className="px-8 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors font-medium"
          >
            {searching ? 'Searching...' : 'Search'}
          </button>
        </div>

        <p className="text-sm text-gray-500">
          Semantic search powered by vector embeddings
        </p>
      </form>

      {searching && (
        <div className="text-center py-12">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
          <p className="mt-4 text-gray-600">Searching knowledge base...</p>
        </div>
      )}

      {error && (
        <div className="bg-red-50 text-red-800 border border-red-200 rounded-lg p-4 mb-6">
          {error}
        </div>
      )}

      {!searching && hasSearched && (
        <div>
          <div className="mb-4 flex justify-between items-center">
            <h2 className="text-xl font-semibold text-gray-800">
              {results.length > 0
                ? `Found ${results.length} result${results.length !== 1 ? 's' : ''}`
                : 'No results found'}
            </h2>
          </div>

          {results.length > 0 ? (
            <div className="space-y-4">
              {results.map((result, index) => (
                <div
                  key={`${result.chunk_id}-${index}`}
                  className="bg-white border border-gray-200 rounded-lg p-5 hover:shadow-md transition-shadow"
                >
                  <div className="flex justify-between items-start mb-3">
                    <div>
                      <h3 className="font-medium text-gray-900 text-lg">
                        {result.document_title}
                      </h3>
                      <p className="text-sm text-gray-500 mt-1">
                        Chunk #{result.chunk_index + 1}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span
                        className={`px-3 py-1 rounded-full text-sm font-medium ${
                          result.score > 0.8
                            ? 'bg-green-100 text-green-800'
                            : result.score > 0.6
                            ? 'bg-yellow-100 text-yellow-800'
                            : 'bg-gray-100 text-gray-800'
                        }`}
                      >
                        {formatScore(result.score)}
                      </span>
                    </div>
                  </div>

                  <div className="text-gray-700 leading-relaxed bg-gray-50 p-4 rounded border-l-4 border-blue-500">
                    {highlightQuery(result.content, query)}
                  </div>

                  <div className="mt-3 text-xs text-gray-400">
                    Document ID: {result.document_id}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12 bg-gray-50 rounded-lg">
              <svg
                className="mx-auto h-12 w-12 text-gray-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              <p className="mt-4 text-gray-600">
                No results found for "{query}". Try a different search query.
              </p>
            </div>
          )}
        </div>
      )}

      {!hasSearched && !searching && (
        <div className="text-center py-12 bg-gray-50 rounded-lg">
          <svg
            className="mx-auto h-16 w-16 text-gray-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
            />
          </svg>
          <p className="mt-4 text-gray-600 text-lg">
            Enter a query to search your knowledge base
          </p>
          <p className="mt-2 text-gray-500 text-sm">
            Our semantic search will find the most relevant content
          </p>
        </div>
      )}
    </div>
  );
};

export default Search;
