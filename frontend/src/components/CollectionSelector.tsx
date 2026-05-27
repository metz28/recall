import React from 'react';
import { useCollections } from '../contexts/CollectionContext';

interface CollectionSelectorProps {
  showAllOption?: boolean;
  onChange?: (collection: string | null) => void;
}

const CollectionSelector: React.FC<CollectionSelectorProps> = ({
  showAllOption = true,
  onChange
}) => {
  const { collections, activeCollection, setActiveCollection, loading } = useCollections();

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value === '' ? null : e.target.value;
    setActiveCollection(value);
    if (onChange) {
      onChange(value);
    }
  };

  if (loading) {
    return (
      <select disabled className="w-full px-3 py-2 border rounded bg-gray-100">
        <option>Loading collections...</option>
      </select>
    );
  }

  return (
    <select
      value={activeCollection || ''}
      onChange={handleChange}
      className="w-full px-3 py-2 border rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
    >
      {showAllOption && (
        <option value="">All Collections</option>
      )}
      {collections.map((collection) => (
        <option key={collection.name} value={collection.name}>
          {collection.name} ({collection.document_count} docs)
        </option>
      ))}
    </select>
  );
};

export default CollectionSelector;
