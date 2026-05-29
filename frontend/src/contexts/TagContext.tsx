import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import { getTags } from '../api/client';

interface Tag {
  tag: string;
  count: number;
}

interface TagContextType {
  tags: Tag[];
  selectedTags: string[];
  loading: boolean;
  setSelectedTags: (tags: string[]) => void;
  refreshTags: (collection?: string) => Promise<void>;
}

const TagContext = createContext<TagContextType | undefined>(undefined);

export const TagProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [tags, setTags] = useState<Tag[]>([]);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  const refreshTags = useCallback(async (collection?: string) => {
    setLoading(true);
    try {
      const fetchedTags = await getTags(collection);
      setTags(fetchedTags);
    } catch (error) {
      console.error('Failed to fetch tags:', error);
      setTags([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const value: TagContextType = {
    tags,
    selectedTags,
    loading,
    setSelectedTags,
    refreshTags,
  };

  return <TagContext.Provider value={value}>{children}</TagContext.Provider>;
};

export const useTags = (): TagContextType => {
  const context = useContext(TagContext);
  if (!context) {
    throw new Error('useTags must be used within a TagProvider');
  }
  return context;
};
