import React, { useState } from 'react';
import { createShare } from '../api/client';
import type { ShareCreate, ShareResponse } from '../types';

interface ShareModalProps {
  resourceType: 'document' | 'search' | 'collection';
  resourceId?: string;
  metadata?: ShareCreate['metadata'];
  onClose: () => void;
}

const ShareModal: React.FC<ShareModalProps> = ({
  resourceType,
  resourceId,
  metadata,
  onClose
}) => {
  const [expiresInDays, setExpiresInDays] = useState<number | undefined>(undefined);
  const [shareUrl, setShareUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const handleCreateShare = async () => {
    setIsLoading(true);
    setError(null);

    const shareData: ShareCreate = {
      resource_type: resourceType,
      resource_id: resourceId,
      expires_in_days: expiresInDays || undefined,
      access_level: 'view',
      metadata
    };

    try {
      const response: ShareResponse = await createShare(shareData);
      setShareUrl(response.share_url);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create share link');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCopyUrl = () => {
    if (shareUrl) {
      navigator.clipboard.writeText(shareUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const getResourceTitle = () => {
    switch (resourceType) {
      case 'document':
        return 'Document';
      case 'search':
        return `Search: "${metadata?.query || 'N/A'}"`;
      case 'collection':
        return `Collection: ${resourceId || 'N/A'}`;
      default:
        return 'Resource';
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-lg w-full mx-4">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold">Share {getResourceTitle()}</h2>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {!shareUrl ? (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Link Expiration
              </label>
              <select
                value={expiresInDays || ''}
                onChange={(e) => setExpiresInDays(e.target.value ? parseInt(e.target.value) : undefined)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Never expires</option>
                <option value="1">1 day</option>
                <option value="7">7 days</option>
                <option value="30">30 days</option>
                <option value="90">90 days</option>
              </select>
            </div>

            <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 text-sm">
              <p className="text-blue-800">
                <strong>Note:</strong> Anyone with this link will be able to view this {resourceType}.
                The link can be revoked at any time from your share management page.
              </p>
            </div>

            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-800">
                {error}
              </div>
            )}

            <div className="flex justify-end space-x-3">
              <button
                onClick={onClose}
                className="px-4 py-2 text-gray-700 bg-gray-200 rounded-lg hover:bg-gray-300"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateShare}
                disabled={isLoading}
                className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:bg-gray-400"
              >
                {isLoading ? 'Creating...' : 'Create Share Link'}
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-sm text-green-800">
              Share link created successfully!
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Share URL
              </label>
              <div className="flex space-x-2">
                <input
                  type="text"
                  value={shareUrl}
                  readOnly
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-lg bg-gray-50 font-mono text-sm"
                />
                <button
                  onClick={handleCopyUrl}
                  className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 whitespace-nowrap"
                >
                  {copied ? 'Copied!' : 'Copy'}
                </button>
              </div>
            </div>

            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 text-sm">
              <p className="text-yellow-800">
                <strong>Important:</strong> Keep this link secure. Anyone with access can view your {resourceType}.
                You can revoke this link anytime from your share management page.
              </p>
            </div>

            <div className="flex justify-end">
              <button
                onClick={onClose}
                className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600"
              >
                Done
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ShareModal;
