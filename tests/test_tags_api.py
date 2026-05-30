"""
Tests for tags API endpoints and tag filtering functionality.
"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

from main import app


def create_async_context_manager(return_value):
    """Helper to create async context manager mock"""
    mock = MagicMock()
    mock.__aenter__ = AsyncMock(return_value=return_value)
    mock.__aexit__ = AsyncMock(return_value=None)
    return mock


class TestTagsAPI:
    """Test tags management API endpoints"""

    def test_list_tags_empty(self):
        """Test listing tags when no tags exist"""
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[])

        mock_conn = Mock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("aiosqlite.connect", return_value=create_async_context_manager(mock_conn)):
            client = TestClient(app)
            response = client.get("/api/tags")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 0

    def test_list_tags_with_counts(self):
        """Test listing tags with document counts"""
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[
            ("machine-learning", 5),
            ("ai", 3),
            ("deep-learning", 2)
        ])

        mock_conn = Mock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("aiosqlite.connect", return_value=create_async_context_manager(mock_conn)):
            client = TestClient(app)
            response = client.get("/api/tags")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 3
            assert data[0]["tag"] == "machine-learning"
            assert data[0]["count"] == 5
            assert data[1]["tag"] == "ai"
            assert data[1]["count"] == 3

    def test_list_tags_with_collection_filter(self):
        """Test listing tags filtered by collection"""
        mock_cursor = AsyncMock()
        mock_cursor.fetchall = AsyncMock(return_value=[
            ("research", 2),
            ("nlp", 1)
        ])

        mock_conn = Mock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("aiosqlite.connect", return_value=create_async_context_manager(mock_conn)):
            client = TestClient(app)
            response = client.get("/api/tags?collection=research-papers")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2

    def test_get_document_tags_success(self):
        """Test getting tags for a specific document"""
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=(json.dumps(["ai", "ml", "research"]),))

        mock_conn = Mock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("aiosqlite.connect", return_value=create_async_context_manager(mock_conn)):
            client = TestClient(app)
            response = client.get("/api/tags/documents/123/tags")

            assert response.status_code == 200
            data = response.json()
            assert data["document_id"] == 123
            assert len(data["tags"]) == 3
            assert "ai" in data["tags"]

    def test_get_document_tags_not_found(self):
        """Test getting tags for non-existent document"""
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)

        mock_conn = Mock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("aiosqlite.connect", return_value=create_async_context_manager(mock_conn)):
            client = TestClient(app)
            response = client.get("/api/tags/documents/999/tags")

            assert response.status_code == 404

    def test_update_document_tags_success(self):
        """Test updating document tags"""
        # Mock for document exists check
        mock_cursor1 = AsyncMock()
        mock_cursor1.fetchone = AsyncMock(return_value=(1,))

        # Mock for getting chunk IDs
        mock_cursor2 = AsyncMock()
        mock_cursor2.fetchall = AsyncMock(return_value=[(101,), (102,), (103,)])

        mock_conn = Mock()
        # First call for update, second for getting chunks
        mock_conn.execute = AsyncMock(side_effect=[mock_cursor1, None, mock_cursor2])
        mock_conn.commit = AsyncMock()

        mock_qdrant = Mock()

        with patch("aiosqlite.connect", return_value=create_async_context_manager(mock_conn)), \
             patch("api.tags.QdrantClient", return_value=mock_qdrant):

            client = TestClient(app)
            response = client.put(
                "/api/tags/documents/1/tags",
                json={"tags": ["ai", "machine-learning", "deep-learning"]}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["document_id"] == 1
            assert len(data["tags"]) == 3

    def test_update_document_tags_not_found(self):
        """Test updating tags for non-existent document"""
        mock_cursor = AsyncMock()
        mock_cursor.fetchone = AsyncMock(return_value=None)

        mock_conn = Mock()
        mock_conn.execute = AsyncMock(return_value=mock_cursor)

        with patch("aiosqlite.connect", return_value=create_async_context_manager(mock_conn)):
            client = TestClient(app)
            response = client.put(
                "/api/tags/documents/999/tags",
                json={"tags": ["ai"]}
            )

            assert response.status_code == 404


class TestTagValidation:
    """Test tag validation logic"""

    def test_validate_tags_too_many(self):
        """Test validation fails with more than 10 tags"""
        client = TestClient(app)
        response = client.put(
            "/api/tags/documents/1/tags",
            json={"tags": [f"tag{i}" for i in range(11)]}
        )

        assert response.status_code == 422
        assert "10 tags" in str(response.json())

    def test_validate_tags_too_long(self):
        """Test validation fails with tag longer than 30 characters"""
        client = TestClient(app)
        response = client.put(
            "/api/tags/documents/1/tags",
            json={"tags": ["a" * 31]}
        )

        assert response.status_code == 422

    def test_validate_tags_invalid_characters(self):
        """Test validation fails with invalid characters"""
        client = TestClient(app)

        # Test spaces
        response = client.put(
            "/api/tags/documents/1/tags",
            json={"tags": ["machine learning"]}
        )
        assert response.status_code == 422

        # Test special characters
        response = client.put(
            "/api/tags/documents/1/tags",
            json={"tags": ["ai@ml"]}
        )
        assert response.status_code == 422


class TestTagFiltering:
    """Test tag filtering in search"""

    def test_search_with_single_tag_filter(self):
        """Test search with single tag filter"""
        mock_results = [
            Mock(
                id="chunk1",
                score=0.95,
                payload={
                    "content": "AI content",
                    "document_id": "doc1",
                    "document_title": "AI Doc",
                    "chunk_index": 0,
                    "collection": "default",
                    "tags": ["ai", "machine-learning"]
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
            response = client.get("/api/search?query=test&tags=ai")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1

    def test_search_with_tags_and_collection(self):
        """Test search with both tag and collection filters"""
        mock_results = [
            Mock(
                id="chunk1",
                score=0.95,
                payload={
                    "content": "Filtered content",
                    "document_id": "doc1",
                    "document_title": "Doc",
                    "chunk_index": 0,
                    "collection": "research",
                    "tags": ["ai"]
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
            response = client.get("/api/search?query=test&tags=ai&collection=research")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
