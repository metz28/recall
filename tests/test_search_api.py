"""
Tests for search API endpoints
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient

from main import app


class TestSearchAPI:
    """Test search API endpoints"""

    def test_search_basic_query(self):
        """Test basic search with query"""
        mock_results = [
            Mock(
                id="chunk1",
                score=0.95,
                payload={
                    "content": "This is test content",
                    "document_id": "doc1",
                    "document_title": "Test Doc",
                    "chunk_index": 0,
                    "collection": "default"
                }
            )
        ]

        with patch("services.embedding.embed_text") as mock_embed, \
             patch("api.search.QdrantClient") as mock_qdrant_class:

            mock_embed.return_value = [0.1] * 384  # Mock embedding
            mock_qdrant = Mock()
            mock_qdrant.search.return_value = mock_results
            mock_qdrant_class.return_value = mock_qdrant

            client = TestClient(app)
            response = client.get("/api/search?query=test")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["chunk_id"] == "chunk1"
            assert data[0]["score"] == 0.95
            assert data[0]["content"] == "This is test content"

    def test_search_with_limit(self):
        """Test search with custom limit"""
        mock_results = [
            Mock(
                id=f"chunk{i}",
                score=0.9 - i * 0.1,
                payload={
                    "content": f"Content {i}",
                    "document_id": f"doc{i}",
                    "document_title": f"Doc {i}",
                    "chunk_index": 0,
                    "collection": "default"
                }
            )
            for i in range(5)
        ]

        with patch("services.embedding.embed_text") as mock_embed, \
             patch("api.search.QdrantClient") as mock_qdrant_class:

            mock_embed.return_value = [0.1] * 384
            mock_qdrant = Mock()
            mock_qdrant.search.return_value = mock_results
            mock_qdrant_class.return_value = mock_qdrant

            client = TestClient(app)
            response = client.get("/api/search?query=test&limit=5")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 5
            # Results should be in order
            assert data[0]["chunk_id"] == "chunk0"
            assert data[4]["chunk_id"] == "chunk4"

    def test_search_with_collection_filter(self):
        """Test search with collection filter"""
        mock_results = [
            Mock(
                id="chunk1",
                score=0.95,
                payload={
                    "content": "Content in collection",
                    "document_id": "doc1",
                    "document_title": "Doc 1",
                    "chunk_index": 0,
                    "collection": "my_collection"
                }
            )
        ]

        with patch("services.embedding.embed_text") as mock_embed, \
             patch("api.search.QdrantClient") as mock_qdrant_class:

            mock_embed.return_value = [0.1] * 384
            mock_qdrant = Mock()
            mock_qdrant.search.return_value = mock_results
            mock_qdrant_class.return_value = mock_qdrant

            client = TestClient(app)
            response = client.get("/api/search?query=test&collection=my_collection")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["collection"] == "my_collection"

            # Verify that the filter was applied
            mock_qdrant.search.assert_called_once()
            call_kwargs = mock_qdrant.search.call_args[1]
            assert call_kwargs["query_filter"] is not None

    def test_search_no_results(self):
        """Test search with no results"""
        with patch("services.embedding.embed_text") as mock_embed, \
             patch("api.search.QdrantClient") as mock_qdrant_class:

            mock_embed.return_value = [0.1] * 384
            mock_qdrant = Mock()
            mock_qdrant.search.return_value = []
            mock_qdrant_class.return_value = mock_qdrant

            client = TestClient(app)
            response = client.get("/api/search?query=nonexistent")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 0

    def test_search_missing_query(self):
        """Test search without query parameter"""
        client = TestClient(app)
        response = client.get("/api/search")

        assert response.status_code == 422  # Validation error

    def test_search_invalid_limit_too_low(self):
        """Test search with limit below minimum"""
        client = TestClient(app)
        response = client.get("/api/search?query=test&limit=0")

        assert response.status_code == 422  # Validation error

    def test_search_invalid_limit_too_high(self):
        """Test search with limit above maximum"""
        client = TestClient(app)
        response = client.get("/api/search?query=test&limit=100")

        assert response.status_code == 422  # Validation error

    def test_search_limit_boundary_values(self):
        """Test search with boundary limit values"""
        with patch("services.embedding.embed_text") as mock_embed, \
             patch("api.search.QdrantClient") as mock_qdrant_class:

            mock_embed.return_value = [0.1] * 384
            mock_qdrant = Mock()
            mock_qdrant.search.return_value = []
            mock_qdrant_class.return_value = mock_qdrant

            client = TestClient(app)

            # Test minimum valid limit (1)
            response = client.get("/api/search?query=test&limit=1")
            assert response.status_code == 200

            # Test maximum valid limit (50)
            response = client.get("/api/search?query=test&limit=50")
            assert response.status_code == 200

    def test_search_with_special_characters_in_query(self):
        """Test search with special characters in query"""
        with patch("services.embedding.embed_text") as mock_embed, \
             patch("api.search.QdrantClient") as mock_qdrant_class:

            mock_embed.return_value = [0.1] * 384
            mock_qdrant = Mock()
            mock_qdrant.search.return_value = []
            mock_qdrant_class.return_value = mock_qdrant

            client = TestClient(app)
            response = client.get("/api/search?query=test%20%26%20special%20%24%20chars")

            assert response.status_code == 200

    def test_search_result_format(self):
        """Test that search results have correct format"""
        mock_results = [
            Mock(
                id="chunk123",
                score=0.85,
                payload={
                    "content": "Test content",
                    "document_id": "doc456",
                    "document_title": "My Document",
                    "chunk_index": 5,
                    "collection": "test_col"
                }
            )
        ]

        with patch("services.embedding.embed_text") as mock_embed, \
             patch("api.search.QdrantClient") as mock_qdrant_class:

            mock_embed.return_value = [0.1] * 384
            mock_qdrant = Mock()
            mock_qdrant.search.return_value = mock_results
            mock_qdrant_class.return_value = mock_qdrant

            client = TestClient(app)
            response = client.get("/api/search?query=test")

            assert response.status_code == 200
            data = response.json()
            result = data[0]

            # Check all expected fields are present
            assert "chunk_id" in result
            assert "score" in result
            assert "content" in result
            assert "document_id" in result
            assert "document_title" in result
            assert "chunk_index" in result
            assert "collection" in result

            # Check values
            assert result["chunk_id"] == "chunk123"
            assert result["score"] == 0.85
            assert result["content"] == "Test content"
            assert result["document_id"] == "doc456"
            assert result["document_title"] == "My Document"
            assert result["chunk_index"] == 5
            assert result["collection"] == "test_col"

    def test_search_with_missing_payload_fields(self):
        """Test search with results missing some payload fields"""
        mock_results = [
            Mock(
                id="chunk1",
                score=0.95,
                payload={
                    "content": "Content",
                    # Missing other fields
                }
            )
        ]

        with patch("services.embedding.embed_text") as mock_embed, \
             patch("api.search.QdrantClient") as mock_qdrant_class:

            mock_embed.return_value = [0.1] * 384
            mock_qdrant = Mock()
            mock_qdrant.search.return_value = mock_results
            mock_qdrant_class.return_value = mock_qdrant

            client = TestClient(app)
            response = client.get("/api/search?query=test")

            assert response.status_code == 200
            data = response.json()
            result = data[0]

            # Should handle missing fields gracefully
            assert result["content"] == "Content"
            assert result["document_id"] is None
            assert result["document_title"] is None
