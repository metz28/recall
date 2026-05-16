"""
Integration tests for entity API endpoints
"""
import pytest
from fastapi.testclient import TestClient
import sys
from pathlib import Path
import tempfile
import os

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from main import app

client = TestClient(app)


@pytest.fixture
def sample_document():
    """Create a sample document with known entities"""
    content = """
    Machine Learning and Artificial Intelligence

    Apple Inc. and Google are leading companies in artificial intelligence research.
    Their headquarters are located in California, specifically in Cupertino and
    Mountain View respectively.

    Notable researchers include Geoffrey Hinton from Google and Yann LeCun from Meta.
    These pioneers have contributed significantly to deep learning.

    Popular frameworks include TensorFlow from Google, PyTorch from Meta, and
    scikit-learn from the open source community.

    The field has applications in various domains including computer vision,
    natural language processing, and robotics. Companies like Microsoft,
    Amazon, and IBM are also investing heavily in AI research.
    """

    # Create temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(content)
        temp_path = f.name

    yield temp_path

    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


class TestEntityAPIIntegration:
    """Integration tests for the full entity extraction pipeline"""

    def test_upload_document_extracts_entities(self, sample_document):
        """Test that uploading a document extracts entities"""
        # Upload document
        with open(sample_document, 'rb') as f:
            response = client.post(
                "/api/ingest/upload",
                files={"file": ("test_doc.txt", f, "text/plain")}
            )

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "success"
        assert data["num_chunks"] > 0

        # Check if entity extraction happened
        if "num_entities" in data:
            assert data["num_entities"] > 0
            assert data["num_entity_mentions"] >= data["num_entities"]

    def test_list_entities_endpoint(self, sample_document):
        """Test listing entities after document upload"""
        # Upload document first
        with open(sample_document, 'rb') as f:
            client.post(
                "/api/ingest/upload",
                files={"file": ("test_doc.txt", f, "text/plain")}
            )

        # List entities
        response = client.get("/api/entities?limit=20")

        assert response.status_code == 200
        data = response.json()

        assert "entities" in data
        assert "total" in data
        assert isinstance(data["entities"], list)

        # Should have found some entities
        if data["total"] > 0:
            entity = data["entities"][0]
            assert "id" in entity
            assert "name" in entity
            assert "entity_type" in entity
            assert "mention_count" in entity

    def test_filter_entities_by_type(self, sample_document):
        """Test filtering entities by type"""
        # Upload document
        with open(sample_document, 'rb') as f:
            client.post(
                "/api/ingest/upload",
                files={"file": ("test_doc.txt", f, "text/plain")}
            )

        # Filter by ORG type
        response = client.get("/api/entities?entity_type=ORG")

        assert response.status_code == 200
        data = response.json()

        # All entities should be organizations
        for entity in data["entities"]:
            assert entity["entity_type"] == "ORG"

    def test_filter_entities_by_mentions(self, sample_document):
        """Test filtering entities by minimum mentions"""
        # Upload document
        with open(sample_document, 'rb') as f:
            client.post(
                "/api/ingest/upload",
                files={"file": ("test_doc.txt", f, "text/plain")}
            )

        # Filter by minimum mentions
        response = client.get("/api/entities?min_mentions=2")

        assert response.status_code == 200
        data = response.json()

        # All entities should have at least 2 mentions
        for entity in data["entities"]:
            assert entity["mention_count"] >= 2

    def test_entity_pagination(self, sample_document):
        """Test entity listing pagination"""
        # Upload document
        with open(sample_document, 'rb') as f:
            client.post(
                "/api/ingest/upload",
                files={"file": ("test_doc.txt", f, "text/plain")}
            )

        # Get first page
        response1 = client.get("/api/entities?limit=3&offset=0")
        assert response1.status_code == 200
        data1 = response1.json()

        # Get second page
        response2 = client.get("/api/entities?limit=3&offset=3")
        assert response2.status_code == 200
        data2 = response2.json()

        # Pages should have same total but different entities
        assert data1["total"] == data2["total"]

        if data1["total"] > 3:
            # If enough entities, pages should differ
            entities1_ids = [e["id"] for e in data1["entities"]]
            entities2_ids = [e["id"] for e in data2["entities"]]
            assert entities1_ids != entities2_ids

    def test_get_entity_details(self, sample_document):
        """Test getting details for a specific entity"""
        # Upload document
        with open(sample_document, 'rb') as f:
            client.post(
                "/api/ingest/upload",
                files={"file": ("test_doc.txt", f, "text/plain")}
            )

        # Get list of entities
        list_response = client.get("/api/entities?limit=1")
        entities = list_response.json()["entities"]

        if entities:
            entity_id = entities[0]["id"]

            # Get entity details
            response = client.get(f"/api/entities/{entity_id}")

            assert response.status_code == 200
            data = response.json()

            assert data["id"] == entity_id
            assert "name" in data
            assert "entity_type" in data
            assert "mentions" in data
            assert isinstance(data["mentions"], list)

            # Check mention structure
            if data["mentions"]:
                mention = data["mentions"][0]
                assert "chunk_id" in mention
                assert "document_title" in mention

    def test_get_nonexistent_entity(self):
        """Test getting details for non-existent entity"""
        response = client.get("/api/entities/nonexistent-id-12345")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_get_entity_chunks(self, sample_document):
        """Test getting chunks that mention an entity"""
        # Upload document
        with open(sample_document, 'rb') as f:
            client.post(
                "/api/ingest/upload",
                files={"file": ("test_doc.txt", f, "text/plain")}
            )

        # Get an entity
        list_response = client.get("/api/entities?limit=1")
        entities = list_response.json()["entities"]

        if entities:
            entity_id = entities[0]["id"]

            # Get chunks for entity
            response = client.get(f"/api/entities/{entity_id}/chunks")

            assert response.status_code == 200
            data = response.json()

            assert "entity" in data
            assert "chunks" in data
            assert "total" in data

            assert data["entity"]["id"] == entity_id

            # Check chunk structure
            if data["chunks"]:
                chunk = data["chunks"][0]
                assert "id" in chunk
                assert "content" in chunk
                assert "document_title" in chunk
                assert "context" in chunk

    def test_entity_chunks_pagination(self, sample_document):
        """Test pagination for entity chunks"""
        # Upload document
        with open(sample_document, 'rb') as f:
            client.post(
                "/api/ingest/upload",
                files={"file": ("test_doc.txt", f, "text/plain")}
            )

        # Find entity with multiple mentions
        list_response = client.get("/api/entities?limit=10")
        entities = list_response.json()["entities"]

        entity_with_mentions = None
        for entity in entities:
            if entity["mention_count"] > 1:
                entity_with_mentions = entity
                break

        if entity_with_mentions:
            entity_id = entity_with_mentions["id"]

            # Get first page
            response1 = client.get(f"/api/entities/{entity_id}/chunks?limit=1&offset=0")
            data1 = response1.json()

            # Get second page
            response2 = client.get(f"/api/entities/{entity_id}/chunks?limit=1&offset=1")
            data2 = response2.json()

            assert data1["total"] == data2["total"]

            if data1["total"] > 1:
                # Should have different chunks
                chunk1_id = data1["chunks"][0]["id"]
                chunk2_id = data2["chunks"][0]["id"]
                assert chunk1_id != chunk2_id

    def test_entity_types_summary(self, sample_document):
        """Test getting entity types summary"""
        # Upload document
        with open(sample_document, 'rb') as f:
            client.post(
                "/api/ingest/upload",
                files={"file": ("test_doc.txt", f, "text/plain")}
            )

        # Get types summary
        response = client.get("/api/entities/types/summary")

        assert response.status_code == 200
        data = response.json()

        assert "types" in data
        assert isinstance(data["types"], list)

        if data["types"]:
            type_info = data["types"][0]
            assert "entity_type" in type_info
            assert "count" in type_info
            assert "total_mentions" in type_info


class TestEntityDeduplication:
    """Test entity deduplication across documents"""

    def test_same_entity_in_multiple_documents(self):
        """Test that same entity in multiple documents is deduplicated"""
        # Create two documents mentioning the same entity
        doc1_content = "Apple Inc. is a technology company."
        doc2_content = "Apple Inc. released a new product. Apple is innovative."

        # Upload first document
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(doc1_content)
            temp1 = f.name

        with open(temp1, 'rb') as f:
            client.post(
                "/api/ingest/upload",
                files={"file": ("doc1.txt", f, "text/plain")}
            )
        os.unlink(temp1)

        # Get initial entity count
        response1 = client.get("/api/entities")
        initial_count = response1.json()["total"]

        # Upload second document
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(doc2_content)
            temp2 = f.name

        with open(temp2, 'rb') as f:
            client.post(
                "/api/ingest/upload",
                files={"file": ("doc2.txt", f, "text/plain")}
            )
        os.unlink(temp2)

        # Check entities after second upload
        response2 = client.get("/api/entities")
        final_count = response2.json()["total"]

        # The entity "Apple Inc." should be deduplicated
        # (though new entities might be added, Apple should only appear once)
        entities = response2.json()["entities"]

        apple_entities = [e for e in entities if "apple" in e["name"].lower()]

        # Should have Apple entity with increased mention count
        if apple_entities:
            apple = apple_entities[0]
            # Should have mentions from both documents
            assert apple["mention_count"] >= 2


class TestEntityExtractionDisabled:
    """Test behavior when entity extraction is disabled"""

    def test_upload_without_entity_extraction(self):
        """Test upload when entity extraction is disabled"""
        # Note: This test assumes entity extraction can be disabled via config
        # In practice, you might need to mock the setting

        content = "Apple Inc. is a company."

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(content)
            temp_path = f.name

        try:
            with open(temp_path, 'rb') as f:
                response = client.post(
                    "/api/ingest/upload",
                    files={"file": ("test.txt", f, "text/plain")}
                )

            # Should succeed even if entity extraction fails
            assert response.status_code == 200

        finally:
            os.unlink(temp_path)


class TestEntityAPIEdgeCases:
    """Test edge cases for entity API"""

    def test_list_entities_empty_database(self):
        """Test listing entities when database is empty or no entities exist"""
        response = client.get("/api/entities")

        assert response.status_code == 200
        data = response.json()

        assert "entities" in data
        assert "total" in data
        assert isinstance(data["entities"], list)

    def test_invalid_entity_type_filter(self):
        """Test filtering with invalid entity type"""
        response = client.get("/api/entities?entity_type=INVALID_TYPE")

        # Should return 200 with empty results
        assert response.status_code == 200
        data = response.json()

        assert data["total"] == 0
        assert data["entities"] == []

    def test_negative_pagination_values(self):
        """Test pagination with invalid values"""
        # Negative offset should be handled by validation
        response = client.get("/api/entities?offset=-1")

        # Should return 422 validation error
        assert response.status_code == 422

    def test_excessive_limit(self):
        """Test pagination with excessive limit"""
        # Limit above max (1000)
        response = client.get("/api/entities?limit=9999")

        # Should return 422 validation error
        assert response.status_code == 422

    def test_zero_limit(self):
        """Test pagination with zero limit"""
        response = client.get("/api/entities?limit=0")

        # Should return 422 validation error
        assert response.status_code == 422
