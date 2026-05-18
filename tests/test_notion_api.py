"""
Integration tests for Notion API endpoints
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from main import app

client = TestClient(app)


class TestNotionStatusEndpoint:
    """Test the Notion status endpoint"""

    def test_notion_status_not_configured(self):
        """Test status when API key is not configured"""
        with patch('api.notion.settings') as mock_settings:
            mock_settings.notion_api_key = None

            response = client.get("/api/notion/status")
            assert response.status_code == 200

            data = response.json()
            assert data["configured"] is False
            assert "not configured" in data["message"]

    def test_notion_status_configured(self):
        """Test status when API key is configured"""
        with patch('api.notion.settings') as mock_settings:
            mock_settings.notion_api_key = "test-key"

            response = client.get("/api/notion/status")
            assert response.status_code == 200

            data = response.json()
            assert data["configured"] is True
            assert "configured" in data["message"]


class TestNotionSearchEndpoint:
    """Test the Notion search endpoint"""

    @patch('api.notion.get_notion_service')
    def test_search_notion_workspace_success(self, mock_service_factory):
        """Test successful Notion workspace search"""
        # Mock service
        mock_service = Mock()
        mock_service.search_pages.return_value = [
            {
                "id": "page-1",
                "url": "https://notion.so/page-1",
                "created_time": "2024-01-01T00:00:00.000Z",
                "last_edited_time": "2024-01-02T00:00:00.000Z",
                "properties": {
                    "Name": {
                        "type": "title",
                        "title": [{"plain_text": "Test Page"}]
                    }
                }
            }
        ]
        mock_service._extract_page_title.return_value = "Test Page"
        mock_service_factory.return_value = mock_service

        response = client.post(
            "/api/notion/search",
            json={"query": "test", "api_key": "test-key"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["pages"]) == 1
        assert data["pages"][0]["id"] == "page-1"
        assert data["pages"][0]["title"] == "Test Page"

    @patch('api.notion.get_notion_service')
    def test_search_notion_workspace_empty_query(self, mock_service_factory):
        """Test search with empty query returns all pages"""
        mock_service = Mock()
        mock_service.search_pages.return_value = []
        mock_service_factory.return_value = mock_service

        response = client.post(
            "/api/notion/search",
            json={"query": ""}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert len(data["pages"]) == 0

    @patch('api.notion.get_notion_service')
    def test_search_notion_workspace_api_error(self, mock_service_factory):
        """Test search with Notion API error"""
        mock_service = Mock()
        mock_service.search_pages.side_effect = ValueError("API Error")
        mock_service_factory.return_value = mock_service

        response = client.post(
            "/api/notion/search",
            json={"query": "test"}
        )

        assert response.status_code == 400
        assert "API Error" in response.json()["detail"]

    def test_search_notion_workspace_invalid_page_size(self):
        """Test search with invalid page size"""
        response = client.post(
            "/api/notion/search",
            json={"query": "test", "page_size": 150}
        )

        assert response.status_code == 422  # Validation error


class TestNotionImportEndpoint:
    """Test the Notion import page endpoint"""

    @patch('api.notion.QdrantClient')
    @patch('api.notion.embed_texts')
    @patch('api.notion.chunk_text')
    @patch('api.notion.get_notion_service')
    @patch('api.notion.aiosqlite.connect')
    async def test_import_notion_page_success(
        self,
        mock_db_connect,
        mock_service_factory,
        mock_chunk,
        mock_embed,
        mock_qdrant
    ):
        """Test successful Notion page import"""
        # Mock Notion service
        mock_service = Mock()
        mock_service.extract_page_content.return_value = (
            "Test Page",
            "This is test content"
        )
        mock_service_factory.return_value = mock_service

        # Mock chunking
        mock_chunk.return_value = [
            {"text": "Chunk 1", "start": 0, "end": 10},
            {"text": "Chunk 2", "start": 10, "end": 20}
        ]

        # Mock embeddings
        mock_embed.return_value = [
            [0.1] * 384,
            [0.2] * 384
        ]

        # Mock database
        mock_db = Mock()
        mock_cursor = Mock()
        mock_db.execute = Mock()
        mock_db.commit = Mock()
        mock_db.__aenter__ = Mock(return_value=mock_db)
        mock_db.__aexit__ = Mock(return_value=None)
        mock_db_connect.return_value = mock_db

        # Mock Qdrant
        mock_qdrant_instance = Mock()
        mock_qdrant.return_value = mock_qdrant_instance

        response = client.post(
            "/api/notion/import-page",
            json={
                "page_id": "test-page-id",
                "api_key": "test-key",
                "tags": ["test", "notion"]
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Test Page"
        assert data["num_chunks"] == 2
        assert "Successfully imported" in data["message"]

    @patch('api.notion.get_notion_service')
    def test_import_notion_page_empty_content(self, mock_service_factory):
        """Test import with empty page content"""
        mock_service = Mock()
        mock_service.extract_page_content.return_value = ("Test Page", "")
        mock_service_factory.return_value = mock_service

        response = client.post(
            "/api/notion/import-page",
            json={"page_id": "test-page-id"}
        )

        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()

    @patch('api.notion.get_notion_service')
    def test_import_notion_page_api_error(self, mock_service_factory):
        """Test import with Notion API error"""
        mock_service = Mock()
        mock_service.extract_page_content.side_effect = ValueError("Page not found")
        mock_service_factory.return_value = mock_service

        response = client.post(
            "/api/notion/import-page",
            json={"page_id": "invalid-page"}
        )

        assert response.status_code == 400
        assert "Page not found" in response.json()["detail"]

    def test_import_notion_page_missing_page_id(self):
        """Test import without page ID"""
        response = client.post(
            "/api/notion/import-page",
            json={}
        )

        assert response.status_code == 422  # Validation error

    @patch('api.notion.QdrantClient')
    @patch('api.notion.embed_texts')
    @patch('api.notion.chunk_text')
    @patch('api.notion.get_notion_service')
    @patch('api.notion.aiosqlite.connect')
    async def test_import_notion_page_with_collection(
        self,
        mock_db_connect,
        mock_service_factory,
        mock_chunk,
        mock_embed,
        mock_qdrant
    ):
        """Test importing page with collection specified"""
        # Mock Notion service
        mock_service = Mock()
        mock_service.extract_page_content.return_value = (
            "Test Page",
            "Content"
        )
        mock_service_factory.return_value = mock_service

        # Mock other dependencies
        mock_chunk.return_value = [{"text": "Chunk", "start": 0, "end": 10}]
        mock_embed.return_value = [[0.1] * 384]

        mock_db = Mock()
        mock_db.execute = Mock()
        mock_db.commit = Mock()
        mock_db.__aenter__ = Mock(return_value=mock_db)
        mock_db.__aexit__ = Mock(return_value=None)
        mock_db_connect.return_value = mock_db

        mock_qdrant_instance = Mock()
        mock_qdrant.return_value = mock_qdrant_instance

        response = client.post(
            "/api/notion/import-page",
            json={
                "page_id": "test-page-id",
                "collection": "my-workspace"
            }
        )

        assert response.status_code == 200


class TestNotionIntegration:
    """End-to-end integration tests"""

    @patch('api.notion.QdrantClient')
    @patch('api.notion.embed_texts')
    @patch('api.notion.chunk_text')
    @patch('api.notion.get_notion_service')
    @patch('api.notion.aiosqlite.connect')
    async def test_full_workflow(
        self,
        mock_db_connect,
        mock_service_factory,
        mock_chunk,
        mock_embed,
        mock_qdrant
    ):
        """Test complete workflow: search -> import -> verify"""
        # Setup mocks
        mock_service = Mock()

        # Mock search
        mock_service.search_pages.return_value = [
            {
                "id": "page-1",
                "url": "https://notion.so/page-1",
                "created_time": "2024-01-01T00:00:00.000Z",
                "last_edited_time": "2024-01-02T00:00:00.000Z",
                "properties": {
                    "Name": {
                        "type": "title",
                        "title": [{"plain_text": "My Page"}]
                    }
                }
            }
        ]
        mock_service._extract_page_title.return_value = "My Page"

        # Mock import
        mock_service.extract_page_content.return_value = (
            "My Page",
            "Page content here"
        )

        mock_service_factory.return_value = mock_service
        mock_chunk.return_value = [{"text": "Chunk", "start": 0, "end": 10}]
        mock_embed.return_value = [[0.1] * 384]

        mock_db = Mock()
        mock_db.execute = Mock()
        mock_db.commit = Mock()
        mock_db.__aenter__ = Mock(return_value=mock_db)
        mock_db.__aexit__ = Mock(return_value=None)
        mock_db_connect.return_value = mock_db

        mock_qdrant_instance = Mock()
        mock_qdrant.return_value = mock_qdrant_instance

        # Step 1: Search
        search_response = client.post(
            "/api/notion/search",
            json={"query": "test"}
        )
        assert search_response.status_code == 200
        pages = search_response.json()["pages"]
        assert len(pages) > 0

        # Step 2: Import first page
        page_id = pages[0]["id"]
        import_response = client.post(
            "/api/notion/import-page",
            json={"page_id": page_id}
        )
        assert import_response.status_code == 200
        assert import_response.json()["title"] == "My Page"


class TestNotionRequestValidation:
    """Test request validation"""

    def test_import_request_validation(self):
        """Test that page_id is required"""
        response = client.post("/api/notion/import-page", json={})
        assert response.status_code == 422

    def test_search_request_defaults(self):
        """Test search request with defaults"""
        with patch('api.notion.get_notion_service') as mock_factory:
            mock_service = Mock()
            mock_service.search_pages.return_value = []
            mock_factory.return_value = mock_service

            response = client.post("/api/notion/search", json={})
            assert response.status_code == 200

    def test_import_tags_validation(self):
        """Test that tags must be a list"""
        response = client.post(
            "/api/notion/import-page",
            json={"page_id": "test", "tags": "not-a-list"}
        )
        assert response.status_code == 422


class TestNotionErrorHandling:
    """Test error handling scenarios"""

    @patch('api.notion.get_notion_service')
    def test_network_error_during_import(self, mock_service_factory):
        """Test handling of network errors"""
        mock_service = Mock()
        mock_service.extract_page_content.side_effect = Exception("Network error")
        mock_service_factory.return_value = mock_service

        response = client.post(
            "/api/notion/import-page",
            json={"page_id": "test"}
        )

        assert response.status_code == 500
        assert "error" in response.json()["detail"].lower()

    @patch('api.notion.get_notion_service')
    def test_invalid_api_key(self, mock_service_factory):
        """Test with invalid API key"""
        mock_service_factory.side_effect = ValueError("Invalid API key")

        response = client.post(
            "/api/notion/import-page",
            json={"page_id": "test", "api_key": "invalid"}
        )

        assert response.status_code == 500
