"""
Graph retrieval service for hybrid search
Provides graph-specific operations for entity and chunk retrieval
"""
import aiosqlite
from typing import Optional

from core.config import settings
from core.logging_config import get_logger
from services.graph_service import get_kuzu_connection

logger = get_logger(__name__)


async def get_chunk_entities(chunk_id: str) -> list[str]:
    """
    Get entity names mentioned in a specific chunk

    Args:
        chunk_id: ID of the chunk

    Returns:
        List of entity names (normalized)
    """
    async with aiosqlite.connect(settings.sqlite_path) as db:
        async with db.execute(
            """SELECT DISTINCT e.name
               FROM entity_mentions em
               JOIN entities e ON em.entity_id = e.id
               WHERE em.chunk_id = ?""",
            (chunk_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]


async def get_chunks_by_entities(
    entity_names: list[str],
    limit: int = 10,
    exclude_chunk_ids: set[str] = None,
    collection: Optional[str] = None,
    tags: Optional[str] = None
) -> list[dict]:
    """
    Find chunks that mention any of the given entities

    Args:
        entity_names: List of entity names (normalized)
        limit: Maximum number of chunks to return
        exclude_chunk_ids: Set of chunk IDs to exclude (to avoid duplicates)
        collection: Optional collection filter
        tags: Optional comma-separated tags filter (OR logic)

    Returns:
        List of chunk dictionaries with id, content, document_id, document_title, chunk_index
    """
    if not entity_names:
        return []

    exclude_chunk_ids = exclude_chunk_ids or set()

    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row

        # Build query with placeholders for entity names
        placeholders = ','.join('?' * len(entity_names))
        exclude_placeholders = ','.join('?' * len(exclude_chunk_ids)) if exclude_chunk_ids else ''

        query = f"""
            SELECT DISTINCT c.id, c.content, c.chunk_index, c.document_id,
                   d.title as document_title,
                   COUNT(DISTINCT em.entity_id) as entity_match_count
            FROM chunks c
            JOIN entity_mentions em ON c.id = em.chunk_id
            JOIN entities e ON em.entity_id = e.id
            JOIN documents d ON c.document_id = d.id
            WHERE e.name IN ({placeholders})
        """

        params = list(entity_names)

        if exclude_chunk_ids:
            query += f" AND c.id NOT IN ({exclude_placeholders})"
            params.extend(list(exclude_chunk_ids))

        if collection:
            query += " AND d.collection = ?"
            params.append(collection)

        if tags:
            # Parse tags and build OR filter using json_each
            tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
            if tag_list:
                tag_placeholders = ','.join('?' * len(tag_list))
                query += f" AND EXISTS (SELECT 1 FROM json_each(d.tags) WHERE value IN ({tag_placeholders}))"
                params.extend(tag_list)

        query += """
            GROUP BY c.id
            ORDER BY entity_match_count DESC, c.chunk_index
            LIMIT ?
        """
        params.append(limit)

        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def get_related_entities(
    entity_names: list[str],
    depth: int = 1,
    limit_per_entity: int = 10
) -> list[dict]:
    """
    Get entities related to the given entities via RELATES_TO relationships

    Args:
        entity_names: List of entity names (normalized)
        depth: Number of hops to traverse (1-3)
        limit_per_entity: Maximum related entities per source entity

    Returns:
        List of dictionaries with related_entity, relationship_type, distance
    """
    if not entity_names or depth < 1:
        return []

    conn = get_kuzu_connection()
    related_entities = []

    try:
        # Kuzu query with variable path length
        # Get entities within 'depth' hops via RELATES_TO
        for entity_name in entity_names:
            try:
                result = conn.execute(
                    f"""
                    MATCH path = (e1:Entity {{name: $entity_name}})-[:RELATES_TO*1..{depth}]->(e2:Entity)
                    WHERE e1.name <> e2.name
                    RETURN DISTINCT e2.name as related_entity,
                           e2.type as entity_type,
                           length(path) as distance
                    ORDER BY distance ASC
                    LIMIT {limit_per_entity}
                    """,
                    {"entity_name": entity_name}
                )

                while result.has_next():
                    row = result.get_next()
                    related_entities.append({
                        "source_entity": entity_name,
                        "related_entity": row[0],
                        "entity_type": row[1],
                        "distance": row[2]
                    })
            except Exception as e:
                # Entity might not exist in graph or have no relationships
                logger.warning(f"Could not find related entities for {entity_name}: {e}")
                continue

    except Exception as e:
        logger.error(f"Error in get_related_entities: {e}")

    return related_entities


async def calculate_entity_overlap(
    chunk_entities: list[str],
    query_entities: list[str]
) -> int:
    """
    Calculate the number of common entities between chunk and query

    Args:
        chunk_entities: List of entity names in the chunk
        query_entities: List of entity names in the query

    Returns:
        Count of overlapping entities
    """
    chunk_set = set(e.lower() for e in chunk_entities)
    query_set = set(e.lower() for e in query_entities)
    return len(chunk_set & query_set)


async def get_entity_graph_distance(
    entity1: str,
    entity2: str,
    max_depth: int = 3
) -> Optional[int]:
    """
    Calculate shortest path distance between two entities in the graph

    Args:
        entity1: First entity name (normalized)
        entity2: Second entity name (normalized)
        max_depth: Maximum path length to search

    Returns:
        Distance (number of hops) or None if not connected
    """
    if entity1.lower() == entity2.lower():
        return 0

    conn = get_kuzu_connection()

    try:
        # Find shortest path between entities
        result = conn.execute(
            f"""
            MATCH path = shortestPath((e1:Entity {{name: $entity1}})-[:RELATES_TO*1..{max_depth}]-(e2:Entity {{name: $entity2}}))
            RETURN length(path) as distance
            """,
            {"entity1": entity1, "entity2": entity2}
        )

        if result.has_next():
            row = result.get_next()
            return row[0]

        return None

    except Exception as e:
        # Entities might not be connected or not exist in graph
        return None
