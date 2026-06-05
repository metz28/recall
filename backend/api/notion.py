"""
Notion API endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional
from uuid import UUID
import aiosqlite
from datetime import datetime

from core.config import settings
from core.dependencies import get_current_user
from core.logging_config import get_logger
from models.user import User
from services.notion_service import get_notion_service
from services.chunking import chunk_text
from services.embedding import embed_texts
from models.document import DocumentMetadata
from qdrant_client import QdrantClient

logger = get_logger(__name__)


router = APIRouter()


class NotionPageRequest(BaseModel):
    """Request model for importing a Notion page"""
    page_id: str = Field(..., description="Notion page ID")
    api_key: Optional[str] = Field(None, description="Optional Notion API key override")
    tags: list[str] = Field(default_factory=list, description="Tags to apply to document")
    collection: Optional[str] = Field(None, description="Collection name")


class NotionPageResponse(BaseModel):
    """Response model for Notion page import"""
    document_id: UUID
    title: str
    num_chunks: int
    message: str


class NotionSearchRequest(BaseModel):
    """Request model for searching Notion workspace"""
    query: str = Field("", description="Search query (empty for all pages)")
    api_key: Optional[str] = Field(None, description="Optional Notion API key override")
    page_size: int = Field(100, ge=1, le=100, description="Number of results")


class NotionPageInfo(BaseModel):
    """Information about a Notion page"""
    id: str
    title: str
    url: str
    created_time: str
    last_edited_time: str


class NotionSearchResponse(BaseModel):
    """Response model for Notion search"""
    pages: list[NotionPageInfo]
    total: int


@router.post("/import-page", response_model=NotionPageResponse)
async def import_notion_page(
    request: NotionPageRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Import a Notion page and ingest it into the knowledge base

    This endpoint:
    1. Fetches the page content from Notion
    2. Chunks the text
    3. Generates embeddings
    4. Stores in database and vector store
    5. Extracts entities (if enabled)

    Requires authentication. Imported documents are associated with the current user.
    """
    try:
        # Initialize Notion service
        notion = get_notion_service(api_key=request.api_key)

        # Extract page content
        logger.info(f"Fetching Notion page: {request.page_id}")
        title, content = notion.extract_page_content(request.page_id)

        if not content:
            raise HTTPException(
                status_code=400,
                detail="Page content is empty"
            )

        logger.info(f"Retrieved page: {title} ({len(content)} characters)")

        # Create document metadata
        doc_metadata = DocumentMetadata(
            title=title,
            source_type="notion",
            source_path=f"notion://{request.page_id}",
            file_type="notion",
            file_size=len(content.encode('utf-8')),
            tags=request.tags,
            collection=request.collection
        )

        # Chunk the content
        logger.info(f"Chunking content...")
        chunks = chunk_text(
            content,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap
        )
        doc_metadata.num_chunks = len(chunks)
        logger.info(f"Created {len(chunks)} chunks")

        # Generate embeddings
        logger.info(f"Generating embeddings...")
        chunk_texts = [c["text"] for c in chunks]
        embeddings = embed_texts(chunk_texts)
        logger.info(f"Generated {len(embeddings)} embeddings")

        # Store in SQLite
        logger.info(f"Storing in database...")
        async with aiosqlite.connect(settings.sqlite_path) as db:
            # Insert document
            await db.execute(
                """
                INSERT INTO documents (
                    id, title, source_type, source_path, file_type,
                    file_size, num_chunks, created_at, updated_at,
                    tags, collection, user_id
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(doc_metadata.id),
                    doc_metadata.title,
                    doc_metadata.source_type,
                    doc_metadata.source_path,
                    doc_metadata.file_type,
                    doc_metadata.file_size,
                    doc_metadata.num_chunks,
                    doc_metadata.created_at.isoformat(),
                    doc_metadata.updated_at.isoformat(),
                    ",".join(doc_metadata.tags),
                    doc_metadata.collection,
                    current_user.id
                )
            )

            # Insert chunks
            for i, chunk in enumerate(chunks):
                chunk_id = f"{doc_metadata.id}-chunk-{i}"
                await db.execute(
                    """
                    INSERT INTO chunks (
                        id, document_id, content, chunk_index,
                        start_char, end_char
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk_id,
                        str(doc_metadata.id),
                        chunk["text"],
                        i,
                        chunk["start"],
                        chunk["end"]
                    )
                )

            await db.commit()

        # Store embeddings in Qdrant
        logger.info(f"Storing vectors in Qdrant...")
        qdrant = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)

        points = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_id = f"{doc_metadata.id}-chunk-{i}"
            payload = {
                "document_id": str(doc_metadata.id),
                "chunk_index": i,
                "content": chunk["text"],
                "document_title": doc_metadata.title,
                "source_type": "notion",
                "page_id": request.page_id,
                "user_id": current_user.id
            }

            if doc_metadata.tags:
                payload["tags"] = doc_metadata.tags
            if doc_metadata.collection:
                payload["collection"] = doc_metadata.collection

            points.append({
                "id": chunk_id,
                "vector": embedding,
                "payload": payload
            })

        qdrant.upsert(
            collection_name="recall_chunks",
            points=points
        )

        logger.info(f"Successfully imported Notion page: {title}")

        return NotionPageResponse(
            document_id=doc_metadata.id,
            title=title,
            num_chunks=len(chunks),
            message=f"Successfully imported Notion page with {len(chunks)} chunks"
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error importing Notion page: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/search", response_model=NotionSearchResponse)
async def search_notion_workspace(
    request: NotionSearchRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Search for pages in Notion workspace

    Returns a list of pages matching the query.
    Use an empty query to get all accessible pages.

    Requires authentication.
    """
    try:
        # Initialize Notion service
        notion = get_notion_service(api_key=request.api_key)

        # Search pages
        logger.info(f"Searching Notion workspace: '{request.query}'")
        pages = notion.search_pages(query=request.query, page_size=request.page_size)

        # Extract page info
        page_infos = []
        for page in pages:
            page_info = NotionPageInfo(
                id=page["id"],
                title=notion._extract_page_title(page),
                url=page.get("url", ""),
                created_time=page.get("created_time", ""),
                last_edited_time=page.get("last_edited_time", "")
            )
            page_infos.append(page_info)

        logger.info(f"Found {len(page_infos)} pages")

        return NotionSearchResponse(
            pages=page_infos,
            total=len(page_infos)
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error searching Notion: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/status")
async def notion_status(current_user: User = Depends(get_current_user)):
    """
    Check Notion integration status

    Returns whether Notion API key is configured.

    Requires authentication.
    """
    has_api_key = settings.notion_api_key is not None and settings.notion_api_key != ""

    return {
        "configured": has_api_key,
        "message": "Notion integration is configured" if has_api_key else "Notion API key not configured"
    }
