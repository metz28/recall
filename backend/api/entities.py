"""
Entity API endpoints
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional
import aiosqlite
import json

from core.config import settings
from core.dependencies import get_current_user
from models.user import User

router = APIRouter()


@router.get("/")
async def list_entities(
    entity_type: Optional[str] = Query(None, description="Filter by entity type (PERSON, ORG, etc.)"),
    min_mentions: Optional[int] = Query(None, description="Minimum number of mentions"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of entities to return"),
    offset: int = Query(0, ge=0, description="Number of entities to skip"),
    collection: Optional[str] = Query(None, description="Filter by collection"),
    current_user: User = Depends(get_current_user)
):
    """
    List entities from current user's documents with optional filters and pagination

    Returns:
        List of entities with their metadata
    """
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row

        # Build query with filters - ALWAYS filter by user_id
        if collection:
            # Filter entities by collection AND user - join through documents
            query = """SELECT DISTINCT e.*
                       FROM entities e
                       JOIN entity_mentions em ON e.id = em.entity_id
                       JOIN chunks c ON em.chunk_id = c.id
                       JOIN documents d ON c.document_id = d.id
                       WHERE d.collection = ? AND d.user_id = ?"""
            params = [collection, current_user.id]
        else:
            # Filter entities from user's documents only
            query = """SELECT DISTINCT e.*
                       FROM entities e
                       JOIN entity_mentions em ON e.id = em.entity_id
                       JOIN chunks c ON em.chunk_id = c.id
                       JOIN documents d ON c.document_id = d.id
                       WHERE d.user_id = ?"""
            params = [current_user.id]

        if entity_type:
            query += " AND e.entity_type = ?" if collection else " AND entity_type = ?"
            params.append(entity_type.upper())

        if min_mentions:
            query += " AND e.mention_count >= ?" if collection else " AND mention_count >= ?"
            params.append(min_mentions)

        query += " ORDER BY " + ("e.mention_count" if collection else "mention_count") + " DESC, " + ("e.name" if collection else "name") + " ASC LIMIT ? OFFSET ?"
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
                    except json.JSONDecodeError:
                        entity['variants'] = []
                entities.append(entity)

            # Get total count for pagination
            if collection:
                count_query = """SELECT COUNT(DISTINCT e.id)
                                 FROM entities e
                                 JOIN entity_mentions em ON e.id = em.entity_id
                                 JOIN chunks c ON em.chunk_id = c.id
                                 JOIN documents d ON c.document_id = d.id
                                 WHERE d.collection = ? AND d.user_id = ?"""
                count_params = [collection, current_user.id]
            else:
                count_query = """SELECT COUNT(DISTINCT e.id)
                                 FROM entities e
                                 JOIN entity_mentions em ON e.id = em.entity_id
                                 JOIN chunks c ON em.chunk_id = c.id
                                 JOIN documents d ON c.document_id = d.id
                                 WHERE d.user_id = ?"""
                count_params = [current_user.id]

            if entity_type:
                count_query += " AND e.entity_type = ?" if collection else " AND entity_type = ?"
                count_params.append(entity_type.upper())

            if min_mentions:
                count_query += " AND e.mention_count >= ?" if collection else " AND mention_count >= ?"
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
async def get_entity(
    entity_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get details for a specific entity (only from user's documents)

    Args:
        entity_id: ID of the entity

    Returns:
        Entity details with mentions count
    """
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row

        # Get entity and verify it belongs to user's documents
        async with db.execute(
            """SELECT DISTINCT e.*
               FROM entities e
               JOIN entity_mentions em ON e.id = em.entity_id
               JOIN chunks c ON em.chunk_id = c.id
               JOIN documents d ON c.document_id = d.id
               WHERE e.id = ? AND d.user_id = ?""",
            (entity_id, current_user.id)
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

            # Get mention details (only from user's documents)
            async with db.execute(
                """SELECT em.id, em.context, em.position, c.id as chunk_id,
                          c.chunk_index, c.document_id, d.title as document_title
                   FROM entity_mentions em
                   JOIN chunks c ON em.chunk_id = c.id
                   JOIN documents d ON c.document_id = d.id
                   WHERE em.entity_id = ? AND d.user_id = ?
                   ORDER BY d.title, c.chunk_index""",
                (entity_id, current_user.id)
            ) as mention_cursor:
                mentions = [dict(m) for m in await mention_cursor.fetchall()]

            entity['mentions'] = mentions

            return entity


@router.get("/{entity_id}/chunks")
async def get_entity_chunks(
    entity_id: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user)
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

        # Verify entity exists in user's documents
        async with db.execute(
            """SELECT DISTINCT e.name, e.entity_type
               FROM entities e
               JOIN entity_mentions em ON e.id = em.entity_id
               JOIN chunks c ON em.chunk_id = c.id
               JOIN documents d ON c.document_id = d.id
               WHERE e.id = ? AND d.user_id = ?""",
            (entity_id, current_user.id)
        ) as cursor:
            entity_row = await cursor.fetchone()
            if not entity_row:
                raise HTTPException(status_code=404, detail="Entity not found")

        # Get chunks (only from user's documents)
        async with db.execute(
            """SELECT c.*, em.context, em.position,
                      d.title as document_title, d.id as document_id
               FROM entity_mentions em
               JOIN chunks c ON em.chunk_id = c.id
               JOIN documents d ON c.document_id = d.id
               WHERE em.entity_id = ? AND d.user_id = ?
               ORDER BY d.title, c.chunk_index
               LIMIT ? OFFSET ?""",
            (entity_id, current_user.id, limit, offset)
        ) as cursor:
            chunks = [dict(row) for row in await cursor.fetchall()]

        # Get total count (only from user's documents)
        async with db.execute(
            """SELECT COUNT(*)
               FROM entity_mentions em
               JOIN chunks c ON em.chunk_id = c.id
               JOIN documents d ON c.document_id = d.id
               WHERE em.entity_id = ? AND d.user_id = ?""",
            (entity_id, current_user.id)
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
async def get_entity_types_summary(
    collection: Optional[str] = Query(None, description="Filter by collection"),
    current_user: User = Depends(get_current_user)
):
    """
    Get summary of entity types and their counts for current user's documents

    Returns:
        Dictionary of entity types with counts
    """
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row

        if collection:
            query = """SELECT e.entity_type, COUNT(DISTINCT e.id) as count, SUM(e.mention_count) as total_mentions
                       FROM entities e
                       JOIN entity_mentions em ON e.id = em.entity_id
                       JOIN chunks c ON em.chunk_id = c.id
                       JOIN documents d ON c.document_id = d.id
                       WHERE d.collection = ? AND d.user_id = ?
                       GROUP BY e.entity_type
                       ORDER BY count DESC"""
            params = (collection, current_user.id)
        else:
            query = """SELECT e.entity_type, COUNT(DISTINCT e.id) as count, SUM(e.mention_count) as total_mentions
                       FROM entities e
                       JOIN entity_mentions em ON e.id = em.entity_id
                       JOIN chunks c ON em.chunk_id = c.id
                       JOIN documents d ON c.document_id = d.id
                       WHERE d.user_id = ?
                       GROUP BY e.entity_type
                       ORDER BY count DESC"""
            params = (current_user.id,)

        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()

            return {
                "types": [dict(row) for row in rows]
            }


@router.get("/{entity_id}/relationships")
async def get_entity_relationships(
    entity_id: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user)
):
    """
    Get relationships for a specific entity

    Args:
        entity_id: ID of the entity
        limit: Maximum number of relationships to return
        offset: Number of relationships to skip

    Returns:
        List of relationships where this entity is the source or target
    """
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row

        # Verify entity exists in user's documents
        async with db.execute(
            """SELECT DISTINCT e.name, e.entity_type
               FROM entities e
               JOIN entity_mentions em ON e.id = em.entity_id
               JOIN chunks c ON em.chunk_id = c.id
               JOIN documents d ON c.document_id = d.id
               WHERE e.id = ? AND d.user_id = ?""",
            (entity_id, current_user.id)
        ) as cursor:
            entity_row = await cursor.fetchone()
            if not entity_row:
                raise HTTPException(status_code=404, detail="Entity not found")

        # Get relationships where entity is source or target (only from user's documents)
        async with db.execute(
            """SELECT DISTINCT r.*,
                      e1.name as source_name, e1.entity_type as source_type,
                      e2.name as target_name, e2.entity_type as target_type
               FROM relationships r
               JOIN entities e1 ON r.source_entity_id = e1.id
               JOIN entities e2 ON r.target_entity_id = e2.id
               JOIN chunks c ON r.chunk_id = c.id
               JOIN documents d ON c.document_id = d.id
               WHERE (r.source_entity_id = ? OR r.target_entity_id = ?) AND d.user_id = ?
               ORDER BY r.created_at DESC
               LIMIT ? OFFSET ?""",
            (entity_id, entity_id, current_user.id, limit, offset)
        ) as cursor:
            relationships = [dict(row) for row in await cursor.fetchall()]

        # Get total count (only from user's documents)
        async with db.execute(
            """SELECT COUNT(DISTINCT r.id)
               FROM relationships r
               JOIN chunks c ON r.chunk_id = c.id
               JOIN documents d ON c.document_id = d.id
               WHERE (r.source_entity_id = ? OR r.target_entity_id = ?) AND d.user_id = ?""",
            (entity_id, entity_id, current_user.id)
        ) as cursor:
            total = (await cursor.fetchone())[0]

        return {
            "entity": {
                "id": entity_id,
                "name": dict(entity_row)['name'],
                "type": dict(entity_row)['entity_type']
            },
            "relationships": relationships,
            "total": total,
            "limit": limit,
            "offset": offset
        }


@router.get("/relationships/all")
async def list_all_relationships(
    relationship_type: Optional[str] = Query(None, description="Filter by relationship type"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    collection: Optional[str] = Query(None, description="Filter by collection"),
    current_user: User = Depends(get_current_user)
):
    """
    List all relationships from current user's documents with optional filters

    Args:
        relationship_type: Filter by relationship type (e.g., "works_for", "located_in")
        limit: Maximum number of relationships to return
        offset: Number of relationships to skip

    Returns:
        List of relationships with entity details
    """
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row

        # Build query - ALWAYS filter by user_id
        if collection:
            query = """SELECT DISTINCT r.*,
                              e1.name as source_name, e1.entity_type as source_type,
                              e2.name as target_name, e2.entity_type as target_type
                       FROM relationships r
                       JOIN entities e1 ON r.source_entity_id = e1.id
                       JOIN entities e2 ON r.target_entity_id = e2.id
                       JOIN chunks c ON r.chunk_id = c.id
                       JOIN documents d ON c.document_id = d.id
                       WHERE d.collection = ? AND d.user_id = ?"""
            params = [collection, current_user.id]
        else:
            query = """SELECT DISTINCT r.*,
                              e1.name as source_name, e1.entity_type as source_type,
                              e2.name as target_name, e2.entity_type as target_type
                       FROM relationships r
                       JOIN entities e1 ON r.source_entity_id = e1.id
                       JOIN entities e2 ON r.target_entity_id = e2.id
                       JOIN chunks c ON r.chunk_id = c.id
                       JOIN documents d ON c.document_id = d.id
                       WHERE d.user_id = ?"""
            params = [current_user.id]

        if relationship_type:
            query += " AND r.relationship_type = ?"
            params.append(relationship_type.lower())

        query += " ORDER BY r.created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        async with db.execute(query, params) as cursor:
            relationships = [dict(row) for row in await cursor.fetchall()]

        # Get total count
        if collection:
            count_query = """SELECT COUNT(DISTINCT r.id)
                             FROM relationships r
                             JOIN chunks c ON r.chunk_id = c.id
                             JOIN documents d ON c.document_id = d.id
                             WHERE d.collection = ? AND d.user_id = ?"""
            count_params = [collection, current_user.id]
        else:
            count_query = """SELECT COUNT(DISTINCT r.id)
                             FROM relationships r
                             JOIN chunks c ON r.chunk_id = c.id
                             JOIN documents d ON c.document_id = d.id
                             WHERE d.user_id = ?"""
            count_params = [current_user.id]

        if relationship_type:
            count_query += " AND " + ("r." if collection else "") + "relationship_type = ?"
            count_params.append(relationship_type.lower())

        async with db.execute(count_query, count_params) as cursor:
            total = (await cursor.fetchone())[0]

        return {
            "relationships": relationships,
            "total": total,
            "limit": limit,
            "offset": offset
        }


@router.get("/relationships/types/summary")
async def get_relationship_types_summary(
    collection: Optional[str] = Query(None, description="Filter by collection"),
    current_user: User = Depends(get_current_user)
):
    """
    Get summary of relationship types and their counts for current user's documents

    Returns:
        Dictionary of relationship types with counts
    """
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row

        if collection:
            query = """SELECT r.relationship_type, COUNT(DISTINCT r.id) as count
                       FROM relationships r
                       JOIN chunks c ON r.chunk_id = c.id
                       JOIN documents d ON c.document_id = d.id
                       WHERE d.collection = ? AND d.user_id = ?
                       GROUP BY r.relationship_type
                       ORDER BY count DESC"""
            params = (collection, current_user.id)
        else:
            query = """SELECT r.relationship_type, COUNT(DISTINCT r.id) as count
                       FROM relationships r
                       JOIN chunks c ON r.chunk_id = c.id
                       JOIN documents d ON c.document_id = d.id
                       WHERE d.user_id = ?
                       GROUP BY r.relationship_type
                       ORDER BY count DESC"""
            params = (current_user.id,)

        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()

            return {
                "types": [dict(row) for row in rows]
            }
