"""
Tests for collections API endpoints
"""
import pytest
import aiosqlite
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from main import app
from core.config import settings


@pytest.fixture
async def test_db():
    """Create a test database with sample data"""
    db_path = ":memory:"
    async with aiosqlite.connect(db_path) as db:
        # Create tables
        await db.execute("""
            CREATE TABLE documents (
                id TEXT PRIMARY KEY,
                title TEXT,
                collection TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE chunks (
                id TEXT PRIMARY KEY,
                document_id TEXT,
                content TEXT,
                chunk_index INTEGER,
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
            )
        """)
        await db.execute("""
            CREATE TABLE entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                type TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE entity_mentions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_id INTEGER,
                chunk_id TEXT,
                context TEXT,
                FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE,
                FOREIGN KEY (chunk_id) REFERENCES chunks(id) ON DELETE CASCADE
            )
        """)
        await db.commit()

        # Insert sample data
        await db.execute(
            "INSERT INTO documents VALUES (?, ?, ?, ?, ?)",
            ("doc1", "Test Doc 1", "test_collection", "2024-01-01", "2024-01-01")
        )
        await db.execute(
            "INSERT INTO documents VALUES (?, ?, ?, ?, ?)",
            ("doc2", "Test Doc 2", "test_collection", "2024-01-02", "2024-01-02")
        )
        await db.execute(
            "INSERT INTO documents VALUES (?, ?, ?, ?, ?)",
            ("doc3", "Default Doc", "default", "2024-01-03", "2024-01-03")
        )

        # Insert chunks
        await db.execute(
            "INSERT INTO chunks VALUES (?, ?, ?, ?)",
            ("chunk1", "doc1", "Content 1", 0)
        )
        await db.execute(
            "INSERT INTO chunks VALUES (?, ?, ?, ?)",
            ("chunk2", "doc1", "Content 2", 1)
        )
        await db.execute(
            "INSERT INTO chunks VALUES (?, ?, ?, ?)",
            ("chunk3", "doc2", "Content 3", 0)
        )
        await db.execute(
            "INSERT INTO chunks VALUES (?, ?, ?, ?)",
            ("chunk4", "doc3", "Content 4", 0)
        )

        # Insert entities
        await db.execute(
            "INSERT INTO entities (name, type) VALUES (?, ?)",
            ("Entity 1", "PERSON")
        )
        await db.execute(
            "INSERT INTO entities (name, type) VALUES (?, ?)",
            ("Entity 2", "ORG")
        )

        # Insert entity mentions
        await db.execute(
            "INSERT INTO entity_mentions (entity_id, chunk_id, context) VALUES (?, ?, ?)",
            (1, "chunk1", "context for entity 1")
        )
        await db.execute(
            "INSERT INTO entity_mentions (entity_id, chunk_id, context) VALUES (?, ?, ?)",
            (2, "chunk2", "context for entity 2")
        )

        await db.commit()
        yield db


@pytest.mark.asyncio
class TestCollectionsAPI:
    """Test collections API endpoints"""

    async def test_list_collections_empty(self):
        """Test listing collections when database is empty"""
        with patch("aiosqlite.connect") as mock_connect:
            mock_db = AsyncMock()
            mock_cursor = AsyncMock()
            mock_cursor.fetchall.return_value = []
            mock_db.execute.return_value = mock_cursor
            mock_connect.return_value.__aenter__.return_value = mock_db

            client = TestClient(app)
            response = client.get("/api/collections")

            assert response.status_code == 200
            data = response.json()
            # Should return default collection even when empty
            assert len(data) == 1
            assert data[0]["name"] == "default"
            assert data[0]["document_count"] == 0
            assert data[0]["total_chunks"] == 0

    async def test_list_collections_with_data(self):
        """Test listing collections with existing data"""
        with patch("aiosqlite.connect") as mock_connect:
            mock_db = AsyncMock()
            mock_cursor = AsyncMock()
            mock_cursor.fetchall.return_value = [
                ("collection1", 5, 20),
                ("collection2", 3, 10),
            ]
            mock_db.execute.return_value = mock_cursor
            mock_connect.return_value.__aenter__.return_value = mock_db

            client = TestClient(app)
            response = client.get("/api/collections")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["name"] == "collection1"
            assert data[0]["document_count"] == 5
            assert data[0]["total_chunks"] == 20

    async def test_create_collection_valid_name(self):
        """Test creating collection with valid name"""
        with patch("aiosqlite.connect") as mock_connect:
            mock_db = AsyncMock()
            mock_cursor = AsyncMock()
            mock_cursor.fetchone.return_value = (0, 0)
            mock_db.execute.return_value = mock_cursor
            mock_connect.return_value.__aenter__.return_value = mock_db

            client = TestClient(app)
            response = client.post("/api/collections", json={"name": "test-collection"})

            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "test-collection"
            assert data["document_count"] == 0
            assert data["total_chunks"] == 0

    async def test_create_collection_invalid_name_uppercase(self):
        """Test creating collection with uppercase letters (should be converted)"""
        with patch("aiosqlite.connect") as mock_connect:
            mock_db = AsyncMock()
            mock_cursor = AsyncMock()
            mock_cursor.fetchone.return_value = (0, 0)
            mock_db.execute.return_value = mock_cursor
            mock_connect.return_value.__aenter__.return_value = mock_db

            client = TestClient(app)
            response = client.post("/api/collections", json={"name": "TestCollection"})

            assert response.status_code == 201
            data = response.json()
            # Name should be converted to lowercase
            assert data["name"] == "testcollection"

    async def test_create_collection_invalid_name_special_chars(self):
        """Test creating collection with invalid special characters"""
        client = TestClient(app)
        response = client.post("/api/collections", json={"name": "test@collection!"})

        assert response.status_code == 422  # Validation error

    async def test_create_collection_invalid_name_spaces(self):
        """Test creating collection with spaces"""
        client = TestClient(app)
        response = client.post("/api/collections", json={"name": "test collection"})

        assert response.status_code == 422  # Validation error

    async def test_create_collection_empty_name(self):
        """Test creating collection with empty name"""
        client = TestClient(app)
        response = client.post("/api/collections", json={"name": ""})

        assert response.status_code == 422  # Validation error

    async def test_create_collection_name_too_long(self):
        """Test creating collection with name exceeding max length"""
        client = TestClient(app)
        long_name = "a" * 51  # Max is 50
        response = client.post("/api/collections", json={"name": long_name})

        assert response.status_code == 422  # Validation error

    async def test_delete_collection_success(self):
        """Test deleting an existing collection"""
        with patch("aiosqlite.connect") as mock_connect:
            mock_db = AsyncMock()
            mock_cursor = AsyncMock()
            mock_cursor.fetchone.return_value = (2,)  # 2 documents in collection
            mock_db.execute.return_value = mock_cursor
            mock_db.commit = AsyncMock()
            mock_connect.return_value.__aenter__.return_value = mock_db

            client = TestClient(app)
            response = client.delete("/api/collections/test_collection")

            assert response.status_code == 204

    async def test_delete_collection_not_found(self):
        """Test deleting non-existent collection"""
        with patch("aiosqlite.connect") as mock_connect:
            mock_db = AsyncMock()
            mock_cursor = AsyncMock()
            mock_cursor.fetchone.return_value = (0,)  # No documents
            mock_db.execute.return_value = mock_cursor
            mock_connect.return_value.__aenter__.return_value = mock_db

            client = TestClient(app)
            response = client.delete("/api/collections/nonexistent")

            assert response.status_code == 404
            assert "not found" in response.json()["detail"]

    async def test_delete_default_collection(self):
        """Test that default collection cannot be deleted"""
        client = TestClient(app)
        response = client.delete("/api/collections/default")

        assert response.status_code == 400
        assert "Cannot delete" in response.json()["detail"]

    async def test_get_collection_stats_success(self):
        """Test getting stats for an existing collection"""
        with patch("aiosqlite.connect") as mock_connect:
            mock_db = AsyncMock()

            # First query for document/chunk counts
            mock_cursor1 = AsyncMock()
            mock_cursor1.fetchone.return_value = (5, 20, "2024-01-01", "2024-01-15")

            # Second query for entity count
            mock_cursor2 = AsyncMock()
            mock_cursor2.fetchone.return_value = (10,)

            mock_db.execute.side_effect = [mock_cursor1, mock_cursor2]
            mock_connect.return_value.__aenter__.return_value = mock_db

            client = TestClient(app)
            response = client.get("/api/collections/test_collection/stats")

            assert response.status_code == 200
            data = response.json()
            assert data["collection"] == "test_collection"
            assert data["document_count"] == 5
            assert data["total_chunks"] == 20
            assert data["entity_count"] == 10
            assert data["created_at"] == "2024-01-01"
            assert data["updated_at"] == "2024-01-15"

    async def test_get_collection_stats_not_found(self):
        """Test getting stats for non-existent collection"""
        with patch("aiosqlite.connect") as mock_connect:
            mock_db = AsyncMock()
            mock_cursor = AsyncMock()
            mock_cursor.fetchone.return_value = (0, 0, None, None)
            mock_db.execute.return_value = mock_cursor
            mock_connect.return_value.__aenter__.return_value = mock_db

            client = TestClient(app)
            response = client.get("/api/collections/nonexistent/stats")

            assert response.status_code == 404

    async def test_get_collection_stats_default_empty(self):
        """Test getting stats for empty default collection"""
        with patch("aiosqlite.connect") as mock_connect:
            mock_db = AsyncMock()
            mock_cursor = AsyncMock()
            mock_cursor.fetchone.return_value = (0, 0, None, None)
            mock_db.execute.return_value = mock_cursor
            mock_connect.return_value.__aenter__.return_value = mock_db

            client = TestClient(app)
            response = client.get("/api/collections/default/stats")

            # Default collection should return empty stats, not 404
            assert response.status_code == 200
            data = response.json()
            assert data["collection"] == "default"
            assert data["document_count"] == 0
            assert data["total_chunks"] == 0
            assert data["entity_count"] == 0


class TestCollectionValidation:
    """Test collection name validation"""

    def test_valid_names(self):
        """Test valid collection names"""
        from api.collections import CollectionCreate

        valid_names = [
            "test",
            "test123",
            "test-collection",
            "test_collection",
            "test-123_abc",
            "abc",
            "a1",
        ]

        for name in valid_names:
            collection = CollectionCreate(name=name)
            # Should be lowercase
            assert collection.name == name.lower()
            assert collection.name.islower()

    def test_invalid_names(self):
        """Test invalid collection names"""
        from api.collections import CollectionCreate
        from pydantic import ValidationError

        invalid_names = [
            "test collection",  # Space
            "test@collection",  # Special char
            "test!collection",  # Special char
            "test.collection",  # Period
            "test/collection",  # Slash
            "test\\collection",  # Backslash
        ]

        for name in invalid_names:
            with pytest.raises(ValidationError):
                CollectionCreate(name=name)

    def test_uppercase_conversion(self):
        """Test that uppercase names are converted to lowercase"""
        from api.collections import CollectionCreate

        collection = CollectionCreate(name="TestCollection")
        assert collection.name == "testcollection"

        collection = CollectionCreate(name="TEST-COLLECTION")
        assert collection.name == "test-collection"
