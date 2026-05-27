import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { getCollections } from '../api/client';
import type { Collection } from '../types';

interface CollectionContextType {
  collections: Collection[];
  activeCollection: string | null;
  setActiveCollection: (name: string | null) => void;
  refreshCollections: () => Promise<void>;
  loading: boolean;
}

const CollectionContext = createContext<CollectionContextType | undefined>(undefined);

export const CollectionProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [collections, setCollections] = useState<Collection[]>([]);
  const [activeCollection, setActiveCollection] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshCollections = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getCollections();
      setCollections(data);
    } catch (error) {
      console.error('Failed to load collections:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshCollections();
  }, [refreshCollections]);

  const value: CollectionContextType = {
    collections,
    activeCollection,
    setActiveCollection,
    refreshCollections,
    loading,
  };

  return (
    <CollectionContext.Provider value={value}>
      {children}
    </CollectionContext.Provider>
  );
};

export const useCollections = (): CollectionContextType => {
  const context = useContext(CollectionContext);
  if (context === undefined) {
    throw new Error('useCollections must be used within a CollectionProvider');
  }
  return context;
};
