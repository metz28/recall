import React, { useState } from 'react';
import ShareModal from './ShareModal';
import type { ShareCreate } from '../types';

interface ShareButtonProps {
  resourceType: 'document' | 'search' | 'collection';
  resourceId?: string;
  metadata?: ShareCreate['metadata'];
  buttonText?: string;
  buttonClassName?: string;
}

const ShareButton: React.FC<ShareButtonProps> = ({
  resourceType,
  resourceId,
  metadata,
  buttonText = 'Share',
  buttonClassName = 'px-3 py-1 bg-blue-500 text-white rounded hover:bg-blue-600'
}) => {
  const [isModalOpen, setIsModalOpen] = useState(false);

  return (
    <>
      <button
        onClick={() => setIsModalOpen(true)}
        className={buttonClassName}
        title={`Share this ${resourceType}`}
      >
        <svg
          className="inline-block w-4 h-4 mr-1"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"
          />
        </svg>
        {buttonText}
      </button>

      {isModalOpen && (
        <ShareModal
          resourceType={resourceType}
          resourceId={resourceId}
          metadata={metadata}
          onClose={() => setIsModalOpen(false)}
        />
      )}
    </>
  );
};

export default ShareButton;
