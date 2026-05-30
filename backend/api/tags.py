"""
API endpoints for tag management.
"""
import json
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, field_validator
import re
import aiosqlite
from qdrant_client import QdrantClient

from core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


class TagUpdate(BaseModel):
    """Request model for updating document tags."""
    tags: List[str]

    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v):
        """Validate tag format and constraints."""
        if len(v) > 10:
            raise ValueError("Maximum 10 tags allowed per document")

        validated = []
        for tag in v:
            # Normalize to lowercase
            tag = tag.lower().strip()

            # Validate format: alphanumeric + hyphens/underscores only
            if not re.match(r'^[a-z0-9_-]+$', tag):
                raise ValueError(f"Tag '{tag}' contains invalid characters. Use only lowercase letters, numbers, hyphens, and underscores.")

            # Validate length
            if len(tag) > 30:
                raise ValueError(f"Tag '{tag}' exceeds maximum length of 30 characters")

            validated.append(tag)

        # Remove duplicates while preserving order
        seen = set()
        unique = []
        for tag in validated:
            if tag not in seen:
                seen.add(tag)
                unique.append(tag)

        return unique


class TagResponse(BaseModel):
    """Response model for tag operations."""
    tag: str
    count: int


def validate_and_parse_tags(tags_str: str) -> List[str]:
    """
    Validate and parse comma-separated tags string.

    Args:
        tags_str: Comma-separated tags string

    Returns:
        List of validated tags

    Raises:
        ValueError: If tags are invalid
    """
    if not tags_str or not tags_str.strip():
        return []

    # Split by comma and clean up
    tags = [tag.strip() for tag in tags_str.split(',') if tag.strip()]

    # Use Pydantic validator
    tag_update = TagUpdate(tags=tags)
    return tag_update.tags


@router.get("", response_model=List[TagResponse])
async def list_tags(collection: Optional[str] = Query(None)):
    """
    List all unique tags with document counts.

    Args:
        collection: Optional collection filter

    Returns:
        List of tags with counts
    """
    try:
        async with aiosqlite.connect(settings.sqlite_path) as conn:
            # Build query to extract and count tags
            if collection:
                query = """
                    SELECT tag, COUNT(DISTINCT d.id) as count
                    FROM documents d, json_each(d.tags) as tag
                    WHERE d.collection = ?
                    GROUP BY tag
                    ORDER BY count DESC, tag ASC
                """
                cursor = await conn.execute(query, (collection,))
            else:
                query = """
                    SELECT tag, COUNT(DISTINCT d.id) as count
                    FROM documents d, json_each(d.tags) as tag
                    GROUP BY tag
                    ORDER BY count DESC, tag ASC
                """
                cursor = await conn.execute(query)

            results = await cursor.fetchall()

            return [{"tag": row[0], "count": row[1]} for row in results]

    except Exception as e:
        logger.error(f"Error listing tags: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/{document_id}/tags")
async def get_document_tags(document_id: int):
    """
    Get tags for a specific document.

    Args:
        document_id: Document ID

    Returns:
        Document tags
    """
    try:
        async with aiosqlite.connect(settings.sqlite_path) as conn:
            cursor = await conn.execute("SELECT tags FROM documents WHERE id = ?", (document_id,))
            result = await cursor.fetchone()

            if not result:
                raise HTTPException(status_code=404, detail="Document not found")

            tags = json.loads(result[0]) if result[0] else []
            return {"document_id": document_id, "tags": tags}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document tags: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/documents/{document_id}/tags")
async def update_document_tags(document_id: int, tag_update: TagUpdate):
    """
    Update tags for a specific document.

    Args:
        document_id: Document ID
        tag_update: New tags

    Returns:
        Updated tags
    """
    try:
        async with aiosqlite.connect(settings.sqlite_path) as conn:
            # Verify document exists
            cursor = await conn.execute("SELECT id FROM documents WHERE id = ?", (document_id,))
            if not await cursor.fetchone():
                raise HTTPException(status_code=404, detail="Document not found")

            # Update SQLite
            tags_json = json.dumps(tag_update.tags)
            await conn.execute(
                "UPDATE documents SET tags = ? WHERE id = ?",
                (tags_json, document_id)
            )
            await conn.commit()

        # Update Qdrant payloads for all chunks of this document
        try:
            client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)

            # Get all chunk IDs for this document
            async with aiosqlite.connect(settings.sqlite_path) as conn:
                cursor = await conn.execute("SELECT id FROM chunks WHERE document_id = ?", (document_id,))
                rows = await cursor.fetchall()
                chunk_ids = [row[0] for row in rows]

            # Update payload for each chunk
            if chunk_ids:
                client.set_payload(
                    collection_name="recall_chunks",
                    payload={"tags": tag_update.tags},
                    points=chunk_ids
                )

            logger.info(f"Updated tags for document {document_id}: {tag_update.tags}")

        except Exception as e:
            logger.error(f"Error updating Qdrant payloads: {e}")
            # Non-fatal - SQLite is source of truth

        return {"status": "success", "document_id": document_id, "tags": tag_update.tags}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating document tags: {e}")
        raise HTTPException(status_code=500, detail=str(e))
