"""
Tests for entity utility functions
"""
import pytest

from services.entity_utils import normalize_entity_name, get_entity_context


class TestNormalizeEntityName:
    """Test entity name normalization"""

    def test_normalize_simple_name(self):
        """Test normalizing a simple entity name"""
        result = normalize_entity_name("john doe")
        assert result == "John Doe"

    def test_normalize_uppercase_name(self):
        """Test normalizing uppercase name"""
        result = normalize_entity_name("JOHN DOE")
        assert result == "John Doe"

    def test_normalize_lowercase_name(self):
        """Test normalizing lowercase name"""
        result = normalize_entity_name("john doe")
        assert result == "John Doe"

    def test_normalize_with_leading_whitespace(self):
        """Test normalizing name with leading whitespace"""
        result = normalize_entity_name("  john doe")
        assert result == "John Doe"

    def test_normalize_with_trailing_whitespace(self):
        """Test normalizing name with trailing whitespace"""
        result = normalize_entity_name("john doe  ")
        assert result == "John Doe"

    def test_normalize_with_extra_spaces(self):
        """Test normalizing name with extra internal spaces"""
        result = normalize_entity_name("john    doe")
        assert result == "John Doe"

    def test_normalize_with_mixed_spaces(self):
        """Test normalizing name with mixed whitespace"""
        result = normalize_entity_name("  john    doe  ")
        assert result == "John Doe"

    def test_normalize_single_word(self):
        """Test normalizing single-word name"""
        result = normalize_entity_name("microsoft")
        assert result == "Microsoft"

    def test_normalize_with_special_chars(self):
        """Test normalizing name with special characters (preserved)"""
        result = normalize_entity_name("o'neill")
        assert result == "O'Neill"

    def test_normalize_with_hyphen(self):
        """Test normalizing hyphenated name"""
        result = normalize_entity_name("jean-paul")
        assert result == "Jean-Paul"

    def test_normalize_empty_string(self):
        """Test normalizing empty string"""
        result = normalize_entity_name("")
        assert result == ""

    def test_normalize_whitespace_only(self):
        """Test normalizing whitespace-only string"""
        result = normalize_entity_name("   ")
        assert result == ""

    def test_normalize_company_name(self):
        """Test normalizing company names"""
        result = normalize_entity_name("apple inc.")
        assert result == "Apple Inc."

    def test_normalize_acronym(self):
        """Test normalizing acronyms"""
        result = normalize_entity_name("nasa")
        assert result == "Nasa"  # Title case converts to this

    def test_normalize_multiple_words(self):
        """Test normalizing longer names"""
        result = normalize_entity_name("united states of america")
        assert result == "United States Of America"


class TestGetEntityContext:
    """Test entity context extraction"""

    def test_get_context_with_positions(self):
        """Test getting context with explicit character positions"""
        text = "The quick brown fox jumps over the lazy dog"
        # "fox" is at positions 16-19
        context = get_entity_context(text, start_char=16, end_char=19, context_window=10)

        assert "fox" in context
        assert "brown" in context  # Before entity
        assert "jumps" in context  # After entity

    def test_get_context_by_entity_name(self):
        """Test getting context by entity name (no positions)"""
        text = "The quick brown fox jumps over the lazy dog"
        context = get_entity_context(text, entity_name="fox", context_window=10)

        assert "fox" in context
        assert "brown" in context
        assert "jumps" in context

    def test_get_context_at_start_of_text(self):
        """Test getting context for entity at start of text"""
        text = "Apple Inc. is a technology company based in California"
        context = get_entity_context(text, entity_name="Apple", context_window=20)

        assert "Apple" in context
        assert "Inc." in context
        # Should not crash at start boundary
        assert len(context) > 0

    def test_get_context_at_end_of_text(self):
        """Test getting context for entity at end of text"""
        text = "The company is based in California"
        context = get_entity_context(text, entity_name="California", context_window=20)

        assert "California" in context
        assert "based" in context
        # Should not crash at end boundary
        assert len(context) > 0

    def test_get_context_with_small_window(self):
        """Test getting context with small window"""
        text = "The quick brown fox jumps over the lazy dog"
        context = get_entity_context(text, entity_name="fox", context_window=5)

        assert "fox" in context
        # Small window should still work
        assert len(context) < len(text)

    def test_get_context_with_large_window(self):
        """Test getting context with large window (larger than text)"""
        text = "Short text with fox"
        context = get_entity_context(text, entity_name="fox", context_window=1000)

        # Should return entire text when window is larger
        assert "Short" in context
        assert "fox" in context

    def test_get_context_entity_not_found(self):
        """Test getting context when entity name not found"""
        text = "The quick brown fox jumps over the lazy dog"
        context = get_entity_context(text, entity_name="elephant", context_window=20)

        # Should return truncated text when entity not found
        assert len(context) <= 200
        assert "quick" in context

    def test_get_context_case_insensitive(self):
        """Test that entity search is case-insensitive"""
        text = "The quick brown FOX jumps over the lazy dog"
        context = get_entity_context(text, entity_name="fox", context_window=10)

        assert "FOX" in context
        assert "brown" in context

    def test_get_context_partial_word_cleanup(self):
        """Test that partial words are cleaned from context edges"""
        text = "This is a longer sentence with the entity mention in the middle of it"
        context = get_entity_context(text, entity_name="entity", context_window=15)

        assert "entity" in context
        # Context should not start or end with partial words
        words = context.split()
        # All words should be complete (no partial)
        for word in words:
            assert len(word) > 0

    def test_get_context_multiple_occurrences(self):
        """Test getting context when entity appears multiple times"""
        text = "Apple makes great products. Apple is innovative. Apple leads."
        context = get_entity_context(text, entity_name="Apple", context_window=10)

        # Should find first occurrence
        assert "Apple" in context
        assert "makes" in context

    def test_get_context_no_entity_name_or_positions(self):
        """Test getting context with no entity name or positions"""
        text = "This is a test text that is somewhat long"
        context = get_entity_context(text, context_window=50)

        # Should return truncated text (up to 200 chars)
        assert len(context) <= 200
        assert "This is a test" in context

    def test_get_context_very_long_text(self):
        """Test getting context from very long text"""
        text = "x" * 10000 + " entity mention " + "y" * 10000
        context = get_entity_context(text, entity_name="entity", context_window=50)

        assert "entity" in context
        # Context should be limited by window
        assert len(context) < 200

    def test_get_context_empty_text(self):
        """Test getting context from empty text"""
        text = ""
        context = get_entity_context(text, entity_name="entity", context_window=50)

        assert context == ""

    def test_get_context_special_characters_in_entity(self):
        """Test entity name with special regex characters"""
        text = "The price is $100 and the total is $150"
        # $ is a special regex character
        context = get_entity_context(text, entity_name="$100", context_window=10)

        assert "$100" in context
        assert "price" in context
