"""
Entity API endpoints
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import aiosqlite
import json

from core.config import settings

router = APIRouter()


@router.get("/")
async def list_entities(
    entity_type: Optional[str] = Query(None, description="Filter by entity type (PERSON, ORG, etc.)"),
    min_mentions: Optional[int] = Query(None, description="Minimum number of mentions"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of entities to return"),
    offset: int = Query(0, ge=0, description="Number of entities to skip")
):
    """
    List entities with optional filters and pagination

    Returns:
        List of entities with their metadata
    """
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row

        # Build query with filters
        query = "SELECT * FROM entities WHERE 1=1"
        params = []

        if entity_type:
            query += " AND entity_type = ?"
            params.append(entity_type.upper())

        if min_mentions:
            query += " AND mention_count >= ?"
            params.append(min_mentions)

        query += " ORDER BY mention_count DESC, name ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()

            entities = []
            for row in rows:
                entity = dict(row)
                # Parse variants JSON
                if entity.get('variants'):
                    try:
                        entity['variants'] = json.loads(entity['variants'])
                    except:
                        entity['variants'] = []
                entities.append(entity)

            # Get total count for pagination
            count_query = "SELECT COUNT(*) FROM entities WHERE 1=1"
            count_params = []

            if entity_type:
                count_query += " AND entity_type = ?"
                count_params.append(entity_type.upper())

            if min_mentions:
                count_query += " AND mention_count >= ?"
                count_params.append(min_mentions)

            async with db.execute(count_query, count_params) as count_cursor:
                total = (await count_cursor.fetchone())[0]

            return {
                "entities": entities,
                "total": total,
                "limit": limit,
                "offset": offset
            }


@router.get("/{entity_id}")
async def get_entity(entity_id: str):
    """
    Get details for a specific entity

    Args:
        entity_id: ID of the entity

    Returns:
        Entity details with mentions count
    """
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row

        # Get entity
        async with db.execute(
            "SELECT * FROM entities WHERE id = ?", (entity_id,)
        ) as cursor:
            row = await cursor.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail="Entity not found")

            entity = dict(row)

            # Parse variants JSON
            if entity.get('variants'):
                try:
                    entity['variants'] = json.loads(entity['variants'])
                except:
                    entity['variants'] = []

            # Get mention details
            async with db.execute(
                """SELECT em.id, em.context, em.position, c.id as chunk_id,
                          c.chunk_index, c.document_id, d.title as document_title
                   FROM entity_mentions em
                   JOIN chunks c ON em.chunk_id = c.id
                   JOIN documents d ON c.document_id = d.id
                   WHERE em.entity_id = ?
                   ORDER BY d.title, c.chunk_index""",
                (entity_id,)
            ) as mention_cursor:
                mentions = [dict(m) for m in await mention_cursor.fetchall()]

            entity['mentions'] = mentions

            return entity


@router.get("/{entity_id}/chunks")
async def get_entity_chunks(
    entity_id: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """
    Get chunks that mention a specific entity

    Args:
        entity_id: ID of the entity
        limit: Maximum number of chunks to return
        offset: Number of chunks to skip

    Returns:
        List of chunks with context about the entity mention
    """
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row

        # Verify entity exists
        async with db.execute(
            "SELECT name, entity_type FROM entities WHERE id = ?", (entity_id,)
        ) as cursor:
            entity_row = await cursor.fetchone()
            if not entity_row:
                raise HTTPException(status_code=404, detail="Entity not found")

        # Get chunks
        async with db.execute(
            """SELECT c.*, em.context, em.position,
                      d.title as document_title, d.id as document_id
               FROM entity_mentions em
               JOIN chunks c ON em.chunk_id = c.id
               JOIN documents d ON c.document_id = d.id
               WHERE em.entity_id = ?
               ORDER BY d.title, c.chunk_index
               LIMIT ? OFFSET ?""",
            (entity_id, limit, offset)
        ) as cursor:
            chunks = [dict(row) for row in await cursor.fetchall()]

        # Get total count
        async with db.execute(
            "SELECT COUNT(*) FROM entity_mentions WHERE entity_id = ?",
            (entity_id,)
        ) as cursor:
            total = (await cursor.fetchone())[0]

        return {
            "entity": {
                "id": entity_id,
                "name": dict(entity_row)['name'],
                "type": dict(entity_row)['entity_type']
            },
            "chunks": chunks,
            "total": total,
            "limit": limit,
            "offset": offset
        }


@router.get("/types/summary")
async def get_entity_types_summary():
    """
    Get summary of entity types and their counts

    Returns:
        Dictionary of entity types with counts
    """
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row

        async with db.execute(
            """SELECT entity_type, COUNT(*) as count, SUM(mention_count) as total_mentions
               FROM entities
               GROUP BY entity_type
               ORDER BY count DESC"""
        ) as cursor:
            rows = await cursor.fetchall()

            return {
                "types": [dict(row) for row in rows]
            }
