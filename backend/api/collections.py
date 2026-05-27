"""
Collections API endpoints
"""
import re
import aiosqlite
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime

from core.config import settings
from core.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter()


class CollectionCreate(BaseModel):
    """Request model for creating a collection"""
    name: str = Field(..., min_length=1, max_length=50)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate collection name format"""
        # Convert to lowercase
        v = v.lower()

        # Check format: alphanumeric, hyphens, underscores only
        if not re.match(r'^[a-z0-9_-]+$', v):
            raise ValueError(
                "Collection name must contain only lowercase letters, numbers, hyphens, and underscores"
            )

        return v


class Collection(BaseModel):
    """Collection information with document count"""
    name: str
    document_count: int
    total_chunks: int


class CollectionStats(BaseModel):
    """Detailed collection statistics"""
    collection: str
    document_count: int
    total_chunks: int
    entity_count: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@router.get("", response_model=list[Collection])
async def list_collections():
    """List all collections with document counts"""
    async with aiosqlite.connect(settings.sqlite_path) as db:
        cursor = await db.execute("""
            SELECT
                d.collection,
                COUNT(DISTINCT d.id) as document_count,
                COUNT(c.id) as total_chunks
            FROM documents d
            LEFT JOIN chunks c ON d.id = c.document_id
            WHERE d.collection IS NOT NULL
            GROUP BY d.collection
            ORDER BY d.collection
        """)

        rows = await cursor.fetchall()
        collections = [
            Collection(
                name=row[0],
                document_count=row[1],
                total_chunks=row[2]
            )
            for row in rows
        ]

        # Ensure "default" collection always exists
        if not any(c.name == "default" for c in collections):
            collections.insert(0, Collection(name="default", document_count=0, total_chunks=0))

        return collections


@router.post("", response_model=Collection, status_code=201)
async def create_collection(collection: CollectionCreate):
    """Create or verify a collection exists"""
    # Collections are created implicitly when documents are uploaded
    # This endpoint validates the name and returns the collection info
    async with aiosqlite.connect(settings.sqlite_path) as db:
        cursor = await db.execute("""
            SELECT
                COUNT(DISTINCT d.id) as document_count,
                COUNT(c.id) as total_chunks
            FROM documents d
            LEFT JOIN chunks c ON d.id = c.document_id
            WHERE d.collection = ?
        """, (collection.name,))

        row = await cursor.fetchone()

        return Collection(
            name=collection.name,
            document_count=row[0] if row else 0,
            total_chunks=row[1] if row else 0
        )


@router.delete("/{name}", status_code=204)
async def delete_collection(name: str):
    """Delete a collection and all its documents"""
    # Prevent deletion of default collection
    if name == "default":
        raise HTTPException(
            status_code=400,
            detail="Cannot delete the 'default' collection"
        )

    async with aiosqlite.connect(settings.sqlite_path) as db:
        # Check if collection exists
        cursor = await db.execute(
            "SELECT COUNT(*) FROM documents WHERE collection = ?",
            (name,)
        )
        count = (await cursor.fetchone())[0]

        if count == 0:
            raise HTTPException(
                status_code=404,
                detail=f"Collection '{name}' not found"
            )

        # Delete all documents in the collection (cascade will handle chunks, entities, etc.)
        await db.execute(
            "DELETE FROM documents WHERE collection = ?",
            (name,)
        )
        await db.commit()

        logger.info(f"Deleted collection '{name}' with {count} documents")


@router.get("/{name}/stats", response_model=CollectionStats)
async def get_collection_stats(name: str):
    """Get detailed statistics for a collection"""
    async with aiosqlite.connect(settings.sqlite_path) as db:
        # Get document and chunk counts
        cursor = await db.execute("""
            SELECT
                COUNT(DISTINCT d.id) as document_count,
                COUNT(c.id) as total_chunks,
                MIN(d.created_at) as created_at,
                MAX(d.updated_at) as updated_at
            FROM documents d
            LEFT JOIN chunks c ON d.id = c.document_id
            WHERE d.collection = ?
        """, (name,))

        row = await cursor.fetchone()

        if not row or row[0] == 0:
            # Collection doesn't exist or is empty
            if name != "default":
                raise HTTPException(
                    status_code=404,
                    detail=f"Collection '{name}' not found"
                )
            # Return empty stats for default collection
            return CollectionStats(
                collection=name,
                document_count=0,
                total_chunks=0,
                entity_count=0,
                created_at=None,
                updated_at=None
            )

        document_count, total_chunks, created_at, updated_at = row

        # Get entity count (entities mentioned in this collection's documents)
        cursor = await db.execute("""
            SELECT COUNT(DISTINCT e.id)
            FROM entities e
            JOIN entity_mentions em ON e.id = em.entity_id
            JOIN chunks c ON em.chunk_id = c.id
            JOIN documents d ON c.document_id = d.id
            WHERE d.collection = ?
        """, (name,))

        entity_count = (await cursor.fetchone())[0]

        return CollectionStats(
            collection=name,
            document_count=document_count,
            total_chunks=total_chunks,
            entity_count=entity_count,
            created_at=created_at,
            updated_at=updated_at
        )
