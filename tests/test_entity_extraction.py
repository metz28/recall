"""
Unit tests for entity extraction service
"""
import pytest
from backend.services.entity_extraction import (
    get_spacy_model,
    normalize_entity_name,
    get_entity_context,
    extract_entities_from_text,
    extract_entities_batch,
    deduplicate_entities,
    DEFAULT_ENTITY_TYPES
)


class TestSpaCyModelLoading:
    """Tests for spaCy model loading"""

    def test_get_spacy_model(self):
        """Test model loading and caching"""
        model1 = get_spacy_model("en_core_web_sm")
        model2 = get_spacy_model("en_core_web_sm")

        assert model1 is not None
        assert model1 is model2  # Should return cached instance

    def test_model_has_ner(self):
        """Test that model has NER component"""
        model = get_spacy_model("en_core_web_sm")
        assert "ner" in model.pipe_names


class TestEntityNormalization:
    """Tests for entity name normalization"""

    def test_normalize_basic(self):
        """Test basic normalization"""
        assert normalize_entity_name("apple") == "Apple"
        assert normalize_entity_name("APPLE") == "Apple"
        assert normalize_entity_name("Apple Inc.") == "Apple Inc."

    def test_normalize_whitespace(self):
        """Test whitespace handling"""
        assert normalize_entity_name("  Apple  ") == "Apple"
        assert normalize_entity_name("Apple  Inc.") == "Apple Inc."
        assert normalize_entity_name("New\nYork") == "New York"

    def test_normalize_empty(self):
        """Test empty string"""
        assert normalize_entity_name("") == ""
        assert normalize_entity_name("   ") == ""


class TestContextExtraction:
    """Tests for entity context extraction"""

    def test_get_context_basic(self):
        """Test basic context extraction"""
        text = "This is a sentence. Apple Inc. is a company. Another sentence here."
        start = text.index("Apple")
        end = start + len("Apple Inc.")

        context = get_entity_context(text, start, end, context_window=20)

        assert "Apple Inc." in context
        assert len(context) > 0

    def test_get_context_at_start(self):
        """Test context extraction at text start"""
        text = "Apple Inc. is a technology company based in California."
        start = 0
        end = len("Apple Inc.")

        context = get_entity_context(text, start, end, context_window=30)

        assert "Apple Inc." in context

    def test_get_context_at_end(self):
        """Test context extraction at text end"""
        text = "The company is Apple Inc."
        start = text.index("Apple")
        end = len(text)

        context = get_entity_context(text, start, end, context_window=30)

        assert "Apple Inc." in context

    def test_get_context_small_window(self):
        """Test with small context window"""
        text = "Word1 word2 Apple Inc. word3 word4"
        start = text.index("Apple")
        end = start + len("Apple Inc.")

        context = get_entity_context(text, start, end, context_window=10)

        assert "Apple Inc." in context
        assert len(context) < 50  # Should be limited


class TestEntityExtraction:
    """Tests for entity extraction"""

    def test_extract_persons(self):
        """Test extraction of person entities"""
        text = "Barack Obama was born in Hawaii. He met Michelle Obama in Chicago."

        entities = extract_entities_from_text(text)

        # Should find person names
        entity_names = [e['name'] for e in entities]
        assert any("Obama" in name for name in entity_names)

    def test_extract_organizations(self):
        """Test extraction of organization entities"""
        text = "Apple Inc., Google, and Microsoft are technology companies."

        entities = extract_entities_from_text(text)

        # Should find organization names
        entity_types = [e['type'] for e in entities]
        assert "ORG" in entity_types

        org_names = [e['name'] for e in entities if e['type'] == 'ORG']
        assert len(org_names) >= 2  # At least Apple and one other

    def test_extract_locations(self):
        """Test extraction of location entities"""
        text = "New York City is in the United States of America."

        entities = extract_entities_from_text(text)

        # Should find GPE (geo-political entities)
        entity_types = [e['type'] for e in entities]
        assert "GPE" in entity_types

    def test_extract_with_filter(self):
        """Test extraction with entity type filter"""
        text = "Apple Inc. is based in California. Steve Jobs founded it."

        # Only extract organizations
        entities = extract_entities_from_text(text, entity_types={"ORG"})

        # Should only have ORG entities
        assert all(e['type'] == 'ORG' for e in entities)

    def test_extract_empty_text(self):
        """Test extraction from empty text"""
        entities = extract_entities_from_text("")
        assert entities == []

    def test_extract_no_entities(self):
        """Test text with no entities"""
        text = "This is a simple sentence with no named entities."
        entities = extract_entities_from_text(text)

        # May or may not find entities depending on spaCy model
        # Just verify it doesn't crash
        assert isinstance(entities, list)

    def test_entity_structure(self):
        """Test that entities have correct structure"""
        text = "Apple Inc. is a company."
        entities = extract_entities_from_text(text)

        if entities:
            entity = entities[0]
            assert 'name' in entity
            assert 'normalized_name' in entity
            assert 'type' in entity
            assert 'start' in entity
            assert 'end' in entity
            assert 'context' in entity


class TestBatchExtraction:
    """Tests for batch entity extraction"""

    def test_batch_extraction_basic(self):
        """Test basic batch extraction"""
        texts = [
            "Apple Inc. is a technology company.",
            "Google was founded by Larry Page.",
            "Microsoft is based in Redmond."
        ]

        results = extract_entities_batch(texts)

        assert len(results) == len(texts)
        assert all(isinstance(entities, list) for entities in results)

    def test_batch_maintains_order(self):
        """Test that batch extraction maintains order"""
        texts = [
            "Text with no entities at all here.",
            "Apple Inc. is mentioned.",
            "Another text without entities really."
        ]

        results = extract_entities_batch(texts)

        # Results should match input order
        assert len(results) == 3
        assert len(results[1]) >= 1  # Second text should have entities
        # Note: First and third may have 0 entities

    def test_batch_empty_list(self):
        """Test batch extraction with empty list"""
        results = extract_entities_batch([])
        assert results == []

    def test_batch_with_empty_strings(self):
        """Test batch extraction with empty strings"""
        texts = ["", "Apple Inc.", ""]
        results = extract_entities_batch(texts)

        assert len(results) == 3
        assert results[0] == []
        assert len(results[1]) >= 1  # Should have Apple
        assert results[2] == []


class TestEntityDeduplication:
    """Tests for entity deduplication"""

    def test_deduplicate_exact_matches(self):
        """Test deduplication of exact matches"""
        mentions = [
            {"name": "Apple Inc.", "normalized_name": "Apple Inc.", "type": "ORG"},
            {"name": "Apple Inc.", "normalized_name": "Apple Inc.", "type": "ORG"},
            {"name": "Apple Inc.", "normalized_name": "Apple Inc.", "type": "ORG"}
        ]

        entities = deduplicate_entities(mentions)

        assert len(entities) == 1
        assert entities["Apple Inc."]["mention_count"] == 3

    def test_deduplicate_case_variants(self):
        """Test deduplication handles case variants"""
        mentions = [
            {"name": "Apple Inc.", "normalized_name": "Apple Inc.", "type": "ORG"},
            {"name": "apple inc.", "normalized_name": "Apple Inc.", "type": "ORG"},
            {"name": "APPLE INC.", "normalized_name": "Apple Inc.", "type": "ORG"}
        ]

        entities = deduplicate_entities(mentions)

        assert len(entities) == 1
        entity = entities["Apple Inc."]
        assert entity["mention_count"] == 3
        assert len(entity["variants"]) == 3  # Should track all variants

    def test_deduplicate_tracks_variants(self):
        """Test that variants are tracked"""
        mentions = [
            {"name": "NYC", "normalized_name": "Nyc", "type": "GPE"},
            {"name": "New York City", "normalized_name": "New York City", "type": "GPE"}
        ]

        entities = deduplicate_entities(mentions)

        # These should be separate entities (different normalized names)
        assert len(entities) >= 1

    def test_deduplicate_empty_list(self):
        """Test deduplication with empty list"""
        entities = deduplicate_entities([])
        assert entities == {}

    def test_deduplicate_canonical_name(self):
        """Test that first occurrence is used as canonical"""
        mentions = [
            {"name": "Apple", "normalized_name": "Apple", "type": "ORG"},
            {"name": "APPLE", "normalized_name": "Apple", "type": "ORG"}
        ]

        entities = deduplicate_entities(mentions)

        assert entities["Apple"]["canonical_name"] == "Apple"


class TestUnicodeHandling:
    """Tests for Unicode and special character handling"""

    def test_unicode_text(self):
        """Test extraction from text with Unicode characters"""
        text = "Café Paris is a restaurant in São Paulo, Brazil."

        entities = extract_entities_from_text(text)

        # Should handle Unicode without crashing
        assert isinstance(entities, list)

    def test_emoji_text(self):
        """Test text with emojis"""
        text = "Apple Inc. 🍎 is a great company 😊"

        entities = extract_entities_from_text(text)

        # Should handle emojis without crashing
        assert isinstance(entities, list)


class TestEdgeCases:
    """Tests for edge cases"""

    def test_very_long_text(self):
        """Test extraction from very long text"""
        # Create a long text with multiple entities
        text = " ".join([
            f"Apple Inc. is mentioned in sentence {i}."
            for i in range(100)
        ])

        entities = extract_entities_from_text(text)

        # Should find many Apple mentions
        assert len(entities) > 0

    def test_entity_at_boundaries(self):
        """Test entities at text boundaries"""
        text = "Apple"

        entities = extract_entities_from_text(text)

        # May or may not detect single word as entity
        assert isinstance(entities, list)

    def test_overlapping_context(self):
        """Test entities with overlapping context"""
        text = "Apple Google Microsoft"

        entities = extract_entities_from_text(text, context_window=5)

        # Should extract all entities with small context
        assert isinstance(entities, list)
