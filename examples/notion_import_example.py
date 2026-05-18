"""
Example script for importing Notion pages into Recall

This script demonstrates how to:
1. Check Notion integration status
2. Search for pages in your Notion workspace
3. Import pages into Recall
"""
import requests
import sys
from typing import Optional


BASE_URL = "http://localhost:8000"


def check_status() -> bool:
    """Check if Notion integration is configured"""
    try:
        response = requests.get(f"{BASE_URL}/api/notion/status")
        data = response.json()
        print(f"✓ Notion integration status: {data['message']}")
        return data["configured"]
    except Exception as e:
        print(f"✗ Error checking status: {e}")
        return False


def search_pages(query: str = "", api_key: Optional[str] = None) -> list[dict]:
    """
    Search for pages in Notion workspace

    Args:
        query: Search query (empty string returns all accessible pages)
        api_key: Optional Notion API key override

    Returns:
        List of page objects
    """
    try:
        payload = {"query": query}
        if api_key:
            payload["api_key"] = api_key

        response = requests.post(f"{BASE_URL}/api/notion/search", json=payload)
        response.raise_for_status()

        data = response.json()
        pages = data["pages"]

        print(f"\n🔍 Found {len(pages)} pages")
        for i, page in enumerate(pages, 1):
            print(f"  {i}. {page['title']}")
            print(f"     ID: {page['id']}")
            print(f"     URL: {page['url']}")
            print()

        return pages
    except Exception as e:
        print(f"✗ Error searching pages: {e}")
        return []


def import_page(
    page_id: str,
    tags: Optional[list[str]] = None,
    collection: Optional[str] = None,
    api_key: Optional[str] = None
) -> Optional[dict]:
    """
    Import a Notion page into Recall

    Args:
        page_id: The Notion page ID
        tags: Optional list of tags
        collection: Optional collection name
        api_key: Optional Notion API key override

    Returns:
        Import result or None if failed
    """
    try:
        payload = {"page_id": page_id}

        if tags:
            payload["tags"] = tags
        if collection:
            payload["collection"] = collection
        if api_key:
            payload["api_key"] = api_key

        print(f"\n📥 Importing page {page_id}...")
        response = requests.post(f"{BASE_URL}/api/notion/import-page", json=payload)
        response.raise_for_status()

        data = response.json()
        print(f"✓ {data['message']}")
        print(f"  Document ID: {data['document_id']}")
        print(f"  Title: {data['title']}")
        print(f"  Chunks: {data['num_chunks']}")

        return data
    except requests.exceptions.HTTPError as e:
        print(f"✗ HTTP Error: {e}")
        if e.response is not None:
            print(f"  Detail: {e.response.json().get('detail', 'Unknown error')}")
        return None
    except Exception as e:
        print(f"✗ Error importing page: {e}")
        return None


def import_all_pages(
    query: str = "",
    tags: Optional[list[str]] = None,
    collection: Optional[str] = None,
    api_key: Optional[str] = None,
    max_pages: Optional[int] = None
) -> int:
    """
    Search and import multiple pages

    Args:
        query: Search query
        tags: Tags to apply to all imported pages
        collection: Collection name
        api_key: Optional Notion API key
        max_pages: Maximum number of pages to import (None = all)

    Returns:
        Number of successfully imported pages
    """
    pages = search_pages(query=query, api_key=api_key)

    if not pages:
        print("No pages found to import")
        return 0

    # Limit number of pages if specified
    if max_pages:
        pages = pages[:max_pages]

    success_count = 0
    for i, page in enumerate(pages, 1):
        print(f"\n[{i}/{len(pages)}] Importing: {page['title']}")
        result = import_page(
            page_id=page["id"],
            tags=tags,
            collection=collection,
            api_key=api_key
        )
        if result:
            success_count += 1

    print(f"\n✅ Successfully imported {success_count}/{len(pages)} pages")
    return success_count


def main():
    """Main function"""
    print("=== Notion Import Example ===\n")

    # Check if Notion is configured
    if not check_status():
        print("\n⚠️  Notion API key not configured!")
        print("Please set NOTION_API_KEY in your .env file")
        sys.exit(1)

    # Example 1: Search for specific pages
    print("\n--- Example 1: Search for specific pages ---")
    pages = search_pages(query="notes")

    # Example 2: Import a single page (if any found)
    if pages:
        print("\n--- Example 2: Import first page ---")
        page = pages[0]
        import_page(
            page_id=page["id"],
            tags=["notion", "example"],
            collection="examples"
        )

    # Example 3: Get all accessible pages
    print("\n--- Example 3: List all accessible pages ---")
    all_pages = search_pages(query="")

    # Example 4: Batch import (commented out to prevent accidental mass import)
    # Uncomment to import multiple pages at once
    # print("\n--- Example 4: Batch import ---")
    # import_all_pages(
    #     query="",
    #     tags=["notion", "batch-import"],
    #     collection="notion-workspace",
    #     max_pages=5  # Limit to 5 pages for testing
    # )

    print("\n=== Done ===")


if __name__ == "__main__":
    main()
