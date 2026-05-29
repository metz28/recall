import React, { useState, useEffect, useRef } from 'react';
import { useTags } from '../contexts/TagContext';

const TagSelector: React.FC = () => {
  const { tags, selectedTags, setSelectedTags, refreshTags } = useTags();
  const [showDropdown, setShowDropdown] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Refresh tags on mount
  useEffect(() => {
    refreshTags();
  }, [refreshTags]);

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Toggle tag selection
  const toggleTag = (tag: string) => {
    if (selectedTags.includes(tag)) {
      setSelectedTags(selectedTags.filter(t => t !== tag));
    } else {
      setSelectedTags([...selectedTags, tag]);
    }
  };

  // Clear all selected tags
  const clearAll = () => {
    setSelectedTags([]);
  };

  return (
    <div className="tag-selector" ref={dropdownRef}>
      {/* Selected tags pills */}
      {selectedTags.length > 0 && (
        <div className="selected-tags">
          {selectedTags.map(tag => (
            <span key={tag} className="tag-pill selected">
              {tag}
              <button
                type="button"
                onClick={() => toggleTag(tag)}
                className="tag-remove"
                aria-label={`Remove filter ${tag}`}
              >
                ×
              </button>
            </span>
          ))}
          <button
            type="button"
            onClick={clearAll}
            className="clear-all-btn"
          >
            Clear all
          </button>
        </div>
      )}

      {/* Dropdown toggle button */}
      <button
        type="button"
        onClick={() => setShowDropdown(!showDropdown)}
        className="tag-selector-toggle"
      >
        Filter by tags
        {selectedTags.length > 0 && (
          <span className="selected-count"> ({selectedTags.length})</span>
        )}
        <span className={`dropdown-arrow ${showDropdown ? 'open' : ''}`}>▼</span>
      </button>

      {/* Dropdown list */}
      {showDropdown && (
        <div className="tag-dropdown">
          {tags.length === 0 ? (
            <div className="tag-dropdown-empty">No tags available</div>
          ) : (
            tags.map(tag => (
              <label key={tag.tag} className="tag-checkbox-item">
                <input
                  type="checkbox"
                  checked={selectedTags.includes(tag.tag)}
                  onChange={() => toggleTag(tag.tag)}
                />
                <span className="tag-checkbox-label">
                  <span className="tag-name">{tag.tag}</span>
                  <span className="tag-count">({tag.count})</span>
                </span>
              </label>
            ))
          )}
        </div>
      )}
    </div>
  );
};

export default TagSelector;
