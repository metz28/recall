import React, { useState, useEffect, useRef } from 'react';
import { useTags } from '../contexts/TagContext';

interface TagInputProps {
  value: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
}

const TagInput: React.FC<TagInputProps> = ({ value, onChange, placeholder = 'Add tags (comma-separated)' }) => {
  const [inputValue, setInputValue] = useState('');
  const [showAutocomplete, setShowAutocomplete] = useState(false);
  const [validationError, setValidationError] = useState('');
  const { tags: existingTags } = useTags();
  const inputRef = useRef<HTMLInputElement>(null);
  const autocompleteRef = useRef<HTMLDivElement>(null);

  // Filter existing tags based on input
  const filteredTags = existingTags
    .filter(tag =>
      tag.tag.toLowerCase().includes(inputValue.toLowerCase()) &&
      !value.includes(tag.tag)
    )
    .slice(0, 5);

  // Validate tag format
  const validateTag = (tag: string): string | null => {
    if (!tag) return null;

    const trimmed = tag.trim().toLowerCase();

    if (trimmed.length === 0) return null;
    if (trimmed.length > 30) return 'Tag exceeds maximum length of 30 characters';
    if (!/^[a-z0-9_-]+$/.test(trimmed)) {
      return 'Tag must contain only lowercase letters, numbers, hyphens, and underscores';
    }

    return null;
  };

  // Add tag(s) from input
  const addTags = () => {
    const newTags = inputValue
      .split(',')
      .map(tag => tag.trim().toLowerCase())
      .filter(tag => tag.length > 0);

    if (newTags.length === 0) return;

    // Validate all new tags
    for (const tag of newTags) {
      const error = validateTag(tag);
      if (error) {
        setValidationError(error);
        return;
      }
    }

    // Check max tags limit
    const totalTags = [...new Set([...value, ...newTags])];
    if (totalTags.length > 10) {
      setValidationError('Maximum 10 tags allowed per document');
      return;
    }

    // Add unique tags
    const uniqueTags = [...new Set([...value, ...newTags])];
    onChange(uniqueTags);
    setInputValue('');
    setValidationError('');
    setShowAutocomplete(false);
  };

  // Handle input change
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value;
    setInputValue(newValue);
    setValidationError('');

    // Show autocomplete if typing
    setShowAutocomplete(newValue.length > 0 && !newValue.endsWith(','));
  };

  // Handle input key down
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      addTags();
    }
  };

  // Remove tag
  const removeTag = (tagToRemove: string) => {
    onChange(value.filter(tag => tag !== tagToRemove));
  };

  // Select from autocomplete
  const selectTag = (tag: string) => {
    if (value.length >= 10) {
      setValidationError('Maximum 10 tags allowed per document');
      return;
    }

    if (!value.includes(tag)) {
      onChange([...value, tag]);
    }
    setInputValue('');
    setShowAutocomplete(false);
    inputRef.current?.focus();
  };

  // Close autocomplete when clicking outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        autocompleteRef.current &&
        !autocompleteRef.current.contains(e.target as Node) &&
        inputRef.current &&
        !inputRef.current.contains(e.target as Node)
      ) {
        setShowAutocomplete(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <div className="tag-input-container">
      {/* Tag pills */}
      {value.length > 0 && (
        <div className="tag-pills">
          {value.map(tag => (
            <span key={tag} className="tag-pill">
              {tag}
              <button
                type="button"
                onClick={() => removeTag(tag)}
                className="tag-remove"
                aria-label={`Remove tag ${tag}`}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      {/* Input field */}
      <div className="tag-input-wrapper">
        <input
          ref={inputRef}
          type="text"
          value={inputValue}
          onChange={handleInputChange}
          onKeyDown={handleKeyDown}
          onBlur={addTags}
          placeholder={placeholder}
          className="tag-input"
          disabled={value.length >= 10}
        />

        {/* Autocomplete dropdown */}
        {showAutocomplete && filteredTags.length > 0 && (
          <div ref={autocompleteRef} className="tag-autocomplete">
            {filteredTags.map(tag => (
              <div
                key={tag.tag}
                className="tag-autocomplete-item"
                onClick={() => selectTag(tag.tag)}
              >
                <span className="tag-name">{tag.tag}</span>
                <span className="tag-count">({tag.count})</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Validation error */}
      {validationError && (
        <div className="tag-error">{validationError}</div>
      )}

      {/* Tag count indicator */}
      <div className="tag-count-indicator">
        {value.length}/10 tags
      </div>
    </div>
  );
};

export default TagInput;
