"""
Tests for embedding service
"""
import pytest
import numpy as np
from unittest.mock import patch, MagicMock
from backend.services.embedding import (
    get_embedding_model,
    embed_text,
    embed_texts
)
from backend.core.config import settings


class TestGetEmbeddingModel:
    """Test suite for get_embedding_model function"""

    def test_model_loading(self):
        """Test that model loads successfully"""
        model = get_embedding_model()
        assert model is not None
        assert hasattr(model, 'encode')

    def test_model_caching(self):
        """Test that model is cached (same instance returned)"""
        model1 = get_embedding_model()
        model2 = get_embedding_model()
        assert model1 is model2

    def test_model_type(self):
        """Test that returned model is a SentenceTransformer"""
        from sentence_transformers import SentenceTransformer
        model = get_embedding_model()
        assert isinstance(model, SentenceTransformer)


class TestEmbedText:
    """Test suite for embed_text function"""

    def test_basic_embedding(self):
        """Test basic text embedding"""
        text = "This is a test sentence."
        embedding = embed_text(text)

        assert isinstance(embedding, list)
        assert len(embedding) == settings.embedding_dimension
        assert all(isinstance(val, float) for val in embedding)

    def test_empty_string_embedding(self):
        """Test embedding of empty string"""
        embedding = embed_text("")

        assert isinstance(embedding, list)
        assert len(embedding) == settings.embedding_dimension

    def test_short_text_embedding(self):
        """Test embedding of very short text"""
        embedding = embed_text("Hi")

        assert isinstance(embedding, list)
        assert len(embedding) == settings.embedding_dimension

    def test_long_text_embedding(self):
        """Test embedding of long text"""
        text = "This is a long sentence. " * 100
        embedding = embed_text(text)

        assert isinstance(embedding, list)
        assert len(embedding) == settings.embedding_dimension

    def test_special_characters_embedding(self):
        """Test embedding with special characters"""
        text = "Hello! How are you? I'm #1."
        embedding = embed_text(text)

        assert isinstance(embedding, list)
        assert len(embedding) == settings.embedding_dimension

    def test_unicode_embedding(self):
        """Test embedding with unicode characters"""
        text = "Hello 世界! Bonjour 🌍!"
        embedding = embed_text(text)

        assert isinstance(embedding, list)
        assert len(embedding) == settings.embedding_dimension

    def test_embedding_values_normalized(self):
        """Test that embedding values are reasonable"""
        text = "This is a test."
        embedding = embed_text(text)

        # Check that values are in a reasonable range (typically -1 to 1 for normalized)
        assert all(-10 <= val <= 10 for val in embedding)

    def test_similar_texts_similar_embeddings(self):
        """Test that similar texts produce similar embeddings"""
        text1 = "The cat sat on the mat."
        text2 = "A cat is sitting on a mat."

        embedding1 = embed_text(text1)
        embedding2 = embed_text(text2)

        # Compute cosine similarity
        similarity = cosine_similarity(embedding1, embedding2)

        # Similar texts should have high similarity (> 0.5)
        assert similarity > 0.5

    def test_different_texts_different_embeddings(self):
        """Test that different texts produce different embeddings"""
        text1 = "The weather is sunny today."
        text2 = "Quantum physics is fascinating."

        embedding1 = embed_text(text1)
        embedding2 = embed_text(text2)

        # Different texts should have lower similarity
        similarity = cosine_similarity(embedding1, embedding2)

        # Should be less similar than identical texts
        assert similarity < 1.0


class TestEmbedTexts:
    """Test suite for embed_texts function"""

    def test_batch_embedding(self):
        """Test batch embedding of multiple texts"""
        texts = [
            "First sentence.",
            "Second sentence.",
            "Third sentence."
        ]
        embeddings = embed_texts(texts)

        assert isinstance(embeddings, list)
        assert len(embeddings) == len(texts)
        assert all(isinstance(emb, list) for emb in embeddings)
        assert all(len(emb) == settings.embedding_dimension for emb in embeddings)

    def test_empty_list(self):
        """Test embedding of empty list"""
        embeddings = embed_texts([])

        assert isinstance(embeddings, list)
        assert len(embeddings) == 0

    def test_single_text_batch(self):
        """Test batch embedding with single text"""
        texts = ["Single text."]
        embeddings = embed_texts(texts)

        assert len(embeddings) == 1
        assert len(embeddings[0]) == settings.embedding_dimension

    def test_large_batch(self):
        """Test embedding of large batch"""
        texts = [f"This is sentence number {i}." for i in range(100)]
        embeddings = embed_texts(texts)

        assert len(embeddings) == 100
        assert all(len(emb) == settings.embedding_dimension for emb in embeddings)

    def test_mixed_length_texts(self):
        """Test batch embedding with varying text lengths"""
        texts = [
            "Short.",
            "This is a medium length sentence with more words.",
            "A" * 500  # Very long text
        ]
        embeddings = embed_texts(texts)

        assert len(embeddings) == 3
        assert all(len(emb) == settings.embedding_dimension for emb in embeddings)

    def test_batch_consistency_with_single(self):
        """Test that batch embedding gives same result as single embedding"""
        text = "This is a test sentence."

        single_embedding = embed_text(text)
        batch_embeddings = embed_texts([text])

        # Should be very similar (allowing for small numerical differences)
        assert len(batch_embeddings) == 1
        similarity = cosine_similarity(single_embedding, batch_embeddings[0])
        assert similarity > 0.99

    def test_batch_with_duplicates(self):
        """Test batch embedding with duplicate texts"""
        texts = ["Same text.", "Same text.", "Different text."]
        embeddings = embed_texts(texts)

        assert len(embeddings) == 3
        # First two embeddings should be very similar
        similarity = cosine_similarity(embeddings[0], embeddings[1])
        assert similarity > 0.99

    def test_batch_with_empty_strings(self):
        """Test batch embedding with empty strings included"""
        texts = ["First text.", "", "Third text."]
        embeddings = embed_texts(texts)

        assert len(embeddings) == 3
        assert all(len(emb) == settings.embedding_dimension for emb in embeddings)

    def test_batch_preserves_order(self):
        """Test that batch embedding preserves input order"""
        texts = [
            "Apple",
            "Banana",
            "Cherry"
        ]
        embeddings = embed_texts(texts)

        # Embed individually to verify order
        individual_embeddings = [embed_text(text) for text in texts]

        for batch_emb, indiv_emb in zip(embeddings, individual_embeddings):
            similarity = cosine_similarity(batch_emb, indiv_emb)
            assert similarity > 0.99


# Helper functions

def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Calculate cosine similarity between two vectors"""
    vec1_np = np.array(vec1)
    vec2_np = np.array(vec2)

    dot_product = np.dot(vec1_np, vec2_np)
    norm1 = np.linalg.norm(vec1_np)
    norm2 = np.linalg.norm(vec2_np)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return float(dot_product / (norm1 * norm2))


# Performance tests (optional, can be slow)

class TestEmbeddingPerformance:
    """Performance tests for embedding service"""

    @pytest.mark.slow
    def test_large_batch_performance(self):
        """Test performance with large batch"""
        texts = [f"Test sentence number {i}." for i in range(1000)]
        embeddings = embed_texts(texts)

        assert len(embeddings) == 1000

    @pytest.mark.slow
    def test_very_long_text_embedding(self):
        """Test embedding of very long text"""
        text = "This is a sentence. " * 10000  # Very long text
        embedding = embed_text(text)

        assert len(embedding) == settings.embedding_dimension
