"""
Unit tests for Notion service
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from services.notion_service import NotionService, get_notion_service
from notion_client.errors import APIResponseError


class TestNotionService:
    """Test suite for NotionService"""

    def test_init_with_api_key(self):
        """Test NotionService initialization with API key"""
        service = NotionService(api_key="test-key")
        assert service.api_key == "test-key"
        assert service.client is not None

    def test_init_without_api_key_raises_error(self):
        """Test that initialization fails without API key"""
        with patch('services.notion_service.settings') as mock_settings:
            mock_settings.notion_api_key = None
            with pytest.raises(ValueError, match="Notion API key is required"):
                NotionService()

    @patch('services.notion_service.Client')
    def test_get_page_success(self, mock_client):
        """Test successful page retrieval"""
        # Mock response
        mock_page = {
            "id": "page-123",
            "properties": {
                "Name": {
                    "type": "title",
                    "title": [{"plain_text": "Test Page"}]
                }
            }
        }
        mock_client.return_value.pages.retrieve.return_value = mock_page

        service = NotionService(api_key="test-key")
        result = service.get_page("page-123")

        assert result == mock_page
        mock_client.return_value.pages.retrieve.assert_called_once_with(page_id="page-123")

    @patch('services.notion_service.Client')
    def test_get_page_api_error(self, mock_client):
        """Test page retrieval with API error"""
        mock_client.return_value.pages.retrieve.side_effect = APIResponseError(
            response=Mock(status_code=404),
            message="Page not found",
            code="object_not_found"
        )

        service = NotionService(api_key="test-key")
        with pytest.raises(ValueError, match="Failed to retrieve Notion page"):
            service.get_page("invalid-page")

    @patch('services.notion_service.Client')
    def test_get_block_children_single_page(self, mock_client):
        """Test retrieving block children with single page of results"""
        mock_response = {
            "results": [
                {"id": "block-1", "type": "paragraph"},
                {"id": "block-2", "type": "heading_1"}
            ],
            "has_more": False,
            "next_cursor": None
        }
        mock_client.return_value.blocks.children.list.return_value = mock_response

        service = NotionService(api_key="test-key")
        blocks = service.get_block_children("page-123")

        assert len(blocks) == 2
        assert blocks[0]["id"] == "block-1"
        assert blocks[1]["id"] == "block-2"

    @patch('services.notion_service.Client')
    def test_get_block_children_multiple_pages(self, mock_client):
        """Test retrieving block children with pagination"""
        # First page
        first_response = {
            "results": [{"id": "block-1"}],
            "has_more": True,
            "next_cursor": "cursor-1"
        }
        # Second page
        second_response = {
            "results": [{"id": "block-2"}],
            "has_more": False,
            "next_cursor": None
        }

        mock_client.return_value.blocks.children.list.side_effect = [
            first_response,
            second_response
        ]

        service = NotionService(api_key="test-key")
        blocks = service.get_block_children("page-123")

        assert len(blocks) == 2
        assert mock_client.return_value.blocks.children.list.call_count == 2

    def test_extract_text_from_paragraph_block(self):
        """Test extracting text from paragraph block"""
        block = {
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {"plain_text": "Hello "},
                    {"plain_text": "World"}
                ]
            }
        }

        service = NotionService(api_key="test-key")
        text = service.extract_text_from_block(block)

        assert text == "Hello World"

    def test_extract_text_from_heading_block(self):
        """Test extracting text from heading block"""
        block = {
            "type": "heading_1",
            "heading_1": {
                "rich_text": [
                    {"plain_text": "Chapter 1"}
                ]
            }
        }

        service = NotionService(api_key="test-key")
        text = service.extract_text_from_block(block)

        assert text == "Chapter 1"

    def test_extract_text_from_code_block(self):
        """Test extracting text from code block"""
        block = {
            "type": "code",
            "code": {
                "rich_text": [
                    {"plain_text": "print('hello')"}
                ],
                "language": "python"
            }
        }

        service = NotionService(api_key="test-key")
        text = service.extract_text_from_block(block)

        assert text == "```python\nprint('hello')\n```"

    def test_extract_text_from_empty_block(self):
        """Test extracting text from empty block"""
        block = {
            "type": "paragraph",
            "paragraph": {
                "rich_text": []
            }
        }

        service = NotionService(api_key="test-key")
        text = service.extract_text_from_block(block)

        assert text == ""

    def test_extract_text_from_child_page(self):
        """Test extracting text from child page block"""
        block = {
            "type": "child_page",
            "child_page": {
                "title": "Subpage Title"
            }
        }

        service = NotionService(api_key="test-key")
        text = service.extract_text_from_block(block)

        assert text == "Subpage Title"

    def test_extract_page_title(self):
        """Test extracting title from page object"""
        page = {
            "id": "page-123",
            "properties": {
                "Name": {
                    "type": "title",
                    "title": [
                        {"plain_text": "My "},
                        {"plain_text": "Title"}
                    ]
                }
            }
        }

        service = NotionService(api_key="test-key")
        title = service._extract_page_title(page)

        assert title == "My Title"

    def test_extract_page_title_fallback(self):
        """Test extracting title with fallback to page ID"""
        page = {
            "id": "page-123",
            "properties": {}
        }

        service = NotionService(api_key="test-key")
        title = service._extract_page_title(page)

        assert title == "Notion Page page-123"

    @patch('services.notion_service.Client')
    def test_extract_page_content(self, mock_client):
        """Test extracting full page content"""
        mock_page = {
            "id": "page-123",
            "properties": {
                "Name": {
                    "type": "title",
                    "title": [{"plain_text": "Test Page"}]
                }
            }
        }

        mock_blocks = {
            "results": [
                {
                    "id": "block-1",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"plain_text": "First paragraph"}]
                    },
                    "has_children": False
                },
                {
                    "id": "block-2",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"plain_text": "Second paragraph"}]
                    },
                    "has_children": False
                }
            ],
            "has_more": False,
            "next_cursor": None
        }

        mock_client.return_value.pages.retrieve.return_value = mock_page
        mock_client.return_value.blocks.children.list.return_value = mock_blocks

        service = NotionService(api_key="test-key")
        title, content = service.extract_page_content("page-123")

        assert title == "Test Page"
        assert "First paragraph" in content
        assert "Second paragraph" in content

    @patch('services.notion_service.Client')
    def test_search_pages_no_query(self, mock_client):
        """Test searching all pages"""
        mock_response = {
            "results": [
                {"id": "page-1", "object": "page"},
                {"id": "page-2", "object": "page"}
            ],
            "has_more": False,
            "next_cursor": None
        }
        mock_client.return_value.search.return_value = mock_response

        service = NotionService(api_key="test-key")
        pages = service.search_pages(query="")

        assert len(pages) == 2
        mock_client.return_value.search.assert_called_once()

    @patch('services.notion_service.Client')
    def test_search_pages_with_query(self, mock_client):
        """Test searching pages with query"""
        mock_response = {
            "results": [{"id": "page-1"}],
            "has_more": False,
            "next_cursor": None
        }
        mock_client.return_value.search.return_value = mock_response

        service = NotionService(api_key="test-key")
        pages = service.search_pages(query="test query")

        assert len(pages) == 1
        call_args = mock_client.return_value.search.call_args
        assert call_args[1]["query"] == "test query"

    @patch('services.notion_service.Client')
    def test_search_pages_pagination(self, mock_client):
        """Test searching pages with pagination"""
        first_response = {
            "results": [{"id": "page-1"}],
            "has_more": True,
            "next_cursor": "cursor-1"
        }
        second_response = {
            "results": [{"id": "page-2"}],
            "has_more": False,
            "next_cursor": None
        }

        mock_client.return_value.search.side_effect = [first_response, second_response]

        service = NotionService(api_key="test-key")
        pages = service.search_pages(query="test")

        assert len(pages) == 2
        assert mock_client.return_value.search.call_count == 2

    @patch('services.notion_service.Client')
    def test_get_database(self, mock_client):
        """Test retrieving a database"""
        mock_database = {
            "id": "db-123",
            "title": [{"plain_text": "My Database"}]
        }
        mock_client.return_value.databases.retrieve.return_value = mock_database

        service = NotionService(api_key="test-key")
        result = service.get_database("db-123")

        assert result == mock_database
        mock_client.return_value.databases.retrieve.assert_called_once_with(
            database_id="db-123"
        )

    @patch('services.notion_service.Client')
    def test_query_database(self, mock_client):
        """Test querying a database"""
        mock_response = {
            "results": [
                {"id": "page-1"},
                {"id": "page-2"}
            ],
            "has_more": False,
            "next_cursor": None
        }
        mock_client.return_value.databases.query.return_value = mock_response

        service = NotionService(api_key="test-key")
        pages = service.query_database("db-123")

        assert len(pages) == 2
        mock_client.return_value.databases.query.assert_called_once()

    @patch('services.notion_service.Client')
    def test_extract_nested_blocks(self, mock_client):
        """Test extracting nested block content"""
        nested_blocks = {
            "results": [
                {
                    "id": "nested-1",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"plain_text": "Nested content"}]
                    },
                    "has_children": False
                }
            ],
            "has_more": False,
            "next_cursor": None
        }
        mock_client.return_value.blocks.children.list.return_value = nested_blocks

        service = NotionService(api_key="test-key")
        content = service._extract_nested_blocks("block-123")

        assert "Nested content" in content

    @patch('services.notion_service.Client')
    def test_extract_nested_blocks_max_depth(self, mock_client):
        """Test that nested block extraction respects max depth"""
        service = NotionService(api_key="test-key")
        # Should return empty string when max depth reached
        content = service._extract_nested_blocks("block-123", depth=10, max_depth=10)
        assert content == ""


class TestNotionServiceFactory:
    """Test the factory function"""

    def test_get_notion_service_with_key(self):
        """Test factory function with API key"""
        service = get_notion_service(api_key="test-key")
        assert isinstance(service, NotionService)
        assert service.api_key == "test-key"

    def test_get_notion_service_from_settings(self):
        """Test factory function using settings"""
        with patch('services.notion_service.settings') as mock_settings:
            mock_settings.notion_api_key = "settings-key"
            service = get_notion_service()
            assert isinstance(service, NotionService)
            assert service.api_key == "settings-key"
