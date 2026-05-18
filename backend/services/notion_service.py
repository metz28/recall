"""
Notion API integration service
"""
from typing import Optional
from notion_client import Client
from notion_client.errors import APIResponseError
from tenacity import retry, stop_after_attempt, wait_exponential
from backend.core.config import settings


class NotionService:
    """Service for interacting with Notion API"""

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Notion client

        Args:
            api_key: Notion integration token. If None, uses settings.notion_api_key
        """
        self.api_key = api_key or settings.notion_api_key
        if not self.api_key:
            raise ValueError("Notion API key is required")
        self.client = Client(auth=self.api_key)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def get_page(self, page_id: str) -> dict:
        """
        Retrieve a Notion page by ID

        Args:
            page_id: The Notion page ID

        Returns:
            Page object from Notion API

        Raises:
            APIResponseError: If the API request fails
        """
        try:
            return self.client.pages.retrieve(page_id=page_id)
        except APIResponseError as e:
            raise ValueError(f"Failed to retrieve Notion page: {e}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def get_block_children(self, block_id: str) -> list[dict]:
        """
        Retrieve all child blocks of a block (paginated)

        Args:
            block_id: The block ID to retrieve children from

        Returns:
            List of block objects
        """
        blocks = []
        has_more = True
        start_cursor = None

        try:
            while has_more:
                response = self.client.blocks.children.list(
                    block_id=block_id,
                    start_cursor=start_cursor
                )
                blocks.extend(response.get("results", []))
                has_more = response.get("has_more", False)
                start_cursor = response.get("next_cursor")
        except APIResponseError as e:
            raise ValueError(f"Failed to retrieve block children: {e}")

        return blocks

    def extract_text_from_block(self, block: dict) -> str:
        """
        Extract text content from a Notion block

        Args:
            block: A Notion block object

        Returns:
            Text content of the block
        """
        block_type = block.get("type")
        if not block_type:
            return ""

        block_content = block.get(block_type, {})

        # Handle rich text blocks
        if "rich_text" in block_content:
            rich_text = block_content["rich_text"]
            return "".join([rt.get("plain_text", "") for rt in rich_text])

        # Handle code blocks
        if block_type == "code":
            rich_text = block_content.get("rich_text", [])
            code = "".join([rt.get("plain_text", "") for rt in rich_text])
            language = block_content.get("language", "")
            return f"```{language}\n{code}\n```"

        # Handle child pages
        if block_type == "child_page":
            return block_content.get("title", "")

        return ""

    def extract_page_content(self, page_id: str) -> tuple[str, str]:
        """
        Extract full text content from a Notion page

        Args:
            page_id: The Notion page ID

        Returns:
            Tuple of (page_title, page_content)
        """
        # Get page metadata
        page = self.get_page(page_id)

        # Extract title
        title = self._extract_page_title(page)

        # Get all blocks
        blocks = self.get_block_children(page_id)

        # Extract text from all blocks recursively
        content_parts = []
        for block in blocks:
            text = self.extract_text_from_block(block)
            if text:
                content_parts.append(text)

            # Handle nested blocks
            if block.get("has_children"):
                nested_text = self._extract_nested_blocks(block["id"])
                if nested_text:
                    content_parts.append(nested_text)

        content = "\n\n".join(content_parts)
        return title, content

    def _extract_page_title(self, page: dict) -> str:
        """Extract title from a Notion page object"""
        properties = page.get("properties", {})

        # Try to find title property
        for prop_name, prop_value in properties.items():
            if prop_value.get("type") == "title":
                title_array = prop_value.get("title", [])
                if title_array:
                    return "".join([t.get("plain_text", "") for t in title_array])

        # Fallback to page ID
        return f"Notion Page {page.get('id', 'Unknown')}"

    def _extract_nested_blocks(self, block_id: str, depth: int = 0, max_depth: int = 10) -> str:
        """
        Recursively extract text from nested blocks

        Args:
            block_id: The parent block ID
            depth: Current recursion depth
            max_depth: Maximum recursion depth

        Returns:
            Extracted text content
        """
        if depth >= max_depth:
            return ""

        try:
            blocks = self.get_block_children(block_id)
        except ValueError:
            return ""

        content_parts = []
        for block in blocks:
            text = self.extract_text_from_block(block)
            if text:
                # Indent nested content
                indent = "  " * depth
                content_parts.append(f"{indent}{text}")

            if block.get("has_children"):
                nested_text = self._extract_nested_blocks(
                    block["id"],
                    depth + 1,
                    max_depth
                )
                if nested_text:
                    content_parts.append(nested_text)

        return "\n".join(content_parts)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def search_pages(self, query: str = "", page_size: int = 100) -> list[dict]:
        """
        Search for pages in Notion workspace

        Args:
            query: Search query (empty string returns all pages)
            page_size: Number of results per page

        Returns:
            List of page objects
        """
        pages = []
        has_more = True
        start_cursor = None

        try:
            while has_more:
                response = self.client.search(
                    query=query,
                    page_size=page_size,
                    start_cursor=start_cursor,
                    filter={"property": "object", "value": "page"}
                )
                pages.extend(response.get("results", []))
                has_more = response.get("has_more", False)
                start_cursor = response.get("next_cursor")
        except APIResponseError as e:
            raise ValueError(f"Failed to search Notion pages: {e}")

        return pages

    def get_database(self, database_id: str) -> dict:
        """
        Retrieve a Notion database by ID

        Args:
            database_id: The Notion database ID

        Returns:
            Database object from Notion API
        """
        try:
            return self.client.databases.retrieve(database_id=database_id)
        except APIResponseError as e:
            raise ValueError(f"Failed to retrieve Notion database: {e}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def query_database(self, database_id: str, page_size: int = 100) -> list[dict]:
        """
        Query all pages from a Notion database

        Args:
            database_id: The Notion database ID
            page_size: Number of results per page

        Returns:
            List of page objects from the database
        """
        pages = []
        has_more = True
        start_cursor = None

        try:
            while has_more:
                response = self.client.databases.query(
                    database_id=database_id,
                    page_size=page_size,
                    start_cursor=start_cursor
                )
                pages.extend(response.get("results", []))
                has_more = response.get("has_more", False)
                start_cursor = response.get("next_cursor")
        except APIResponseError as e:
            raise ValueError(f"Failed to query Notion database: {e}")

        return pages


def get_notion_service(api_key: Optional[str] = None) -> NotionService:
    """
    Factory function to create NotionService instance

    Args:
        api_key: Optional Notion API key. If None, uses settings.notion_api_key

    Returns:
        NotionService instance

    Raises:
        ValueError: If no API key is provided or found in settings
    """
    return NotionService(api_key=api_key)
