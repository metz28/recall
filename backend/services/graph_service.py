"""
Graph service for Kuzu database operations
"""

from functools import lru_cache
from pathlib import Path

import kuzu

from core.config import settings


@lru_cache(maxsize=1)
def get_kuzu_connection():
    """Get or create Kuzu database connection (cached)"""
    db_path = Path(settings.kuzu_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    db = kuzu.Database(settings.kuzu_path)
    conn = kuzu.Connection(db)

    print("✅ Kuzu connection established")
    return conn


def store_entities_in_graph(
    entities: list[dict], chunk_id: str, chunk_content: str
) -> None:
    """
    Store entities and their relationships to chunks in Kuzu graph

    Args:
        entities: List of entity dictionaries with keys: normalized_name, type, context
        chunk_id: ID of the chunk
        chunk_content: Content of the chunk
    """
    conn = get_kuzu_connection()

    try:
        # Upsert Chunk node
        # Note: We use MERGE to create if not exists
        conn.execute(
            """
            MERGE (c:Chunk {id: $chunk_id})
            ON CREATE SET c.content = $content
            """,
            {
                "chunk_id": chunk_id,
                "content": chunk_content[:500],
            },  # Limit content length
        )

        # Process each entity
        for entity in entities:
            # Upsert Entity node
            conn.execute(
                """
                MERGE (e:Entity {name: $name})
                ON CREATE SET e.type = $type, e.description = ''
                """,
                {"name": entity["normalized_name"], "type": entity["type"]},
            )

            # Create MENTIONED_IN relationship
            conn.execute(
                """
                MATCH (e:Entity {name: $entity_name})
                MATCH (c:Chunk {id: $chunk_id})
                MERGE (e)-[r:MENTIONED_IN]->(c)
                ON CREATE SET r.context = $context
                """,
                {
                    "entity_name": entity["normalized_name"],
                    "chunk_id": chunk_id,
                    "context": entity.get("context", "")[:200],  # Limit context length
                },
            )

    except Exception as e:
        print(f"⚠️  Error storing entities in graph: {e}")
        # Don't raise - we want ingestion to continue even if graph storage fails


def query_entity_graph(entity_name: str, depth: int = 1) -> dict:
    """
    Query entity neighborhood in the graph

    Args:
        entity_name: Normalized name of the entity
        depth: How many hops to traverse (default 1)

    Returns:
        Dictionary with entity info and related chunks
    """
    conn = get_kuzu_connection()

    try:
        # Get entity and its chunks
        result = conn.execute(
            """
            MATCH (e:Entity {name: $entity_name})-[r:MENTIONED_IN]->(c:Chunk)
            RETURN e.name, e.type, e.description, c.id, c.content, r.context
            """,
            {"entity_name": entity_name},
        )

        entity_info = {
            "name": entity_name,
            "type": None,
            "description": None,
            "chunks": [],
        }

        while result.has_next():
            row = result.get_next()
            if entity_info["type"] is None:
                entity_info["type"] = row[1]
                entity_info["description"] = row[2]

            entity_info["chunks"].append(
                {"chunk_id": row[3], "content": row[4], "context": row[5]}
            )

        return entity_info

    except Exception as e:
        print(f"⚠️  Error querying entity graph: {e}")
        return {
            "name": entity_name,
            "type": None,
            "description": None,
            "chunks": [],
            "error": str(e),
        }


def get_entity_relationships(entity_name: str) -> list[dict]:
    """
    Get relationships between entities (for future use)

    Args:
        entity_name: Normalized name of the entity

    Returns:
        List of related entities
    """
    conn = get_kuzu_connection()

    try:
        # Get entities that co-occur in the same chunks
        result = conn.execute(
            """
            MATCH (e1:Entity {name: $entity_name})-[:MENTIONED_IN]->(c:Chunk)<-[:MENTIONED_IN]-(e2:Entity)
            WHERE e1.name <> e2.name
            RETURN DISTINCT e2.name, e2.type, COUNT(c) as co_occurrences
            ORDER BY co_occurrences DESC
            LIMIT 20
            """,
            {"entity_name": entity_name},
        )

        related_entities = []
        while result.has_next():
            row = result.get_next()
            related_entities.append(
                {"name": row[0], "type": row[1], "co_occurrences": row[2]}
            )

        return related_entities

    except Exception as e:
        print(f"⚠️  Error querying entity relationships: {e}")
        return []


def store_relationships_in_graph(relationships: list[dict]) -> None:
    """
    Store entity relationships in Kuzu graph

    Args:
        relationships: List of relationship dictionaries with keys:
                      source_entity, target_entity, relationship_type, context
    """
    conn = get_kuzu_connection()

    try:
        for rel in relationships:
            # Create RELATES_TO relationship between entities
            conn.execute(
                """
                MATCH (e1:Entity {name: $source_entity})
                MATCH (e2:Entity {name: $target_entity})
                MERGE (e1)-[r:RELATES_TO]->(e2)
                ON CREATE SET r.type = $rel_type, r.context = $context
                """,
                {
                    "source_entity": rel["source_entity"],
                    "target_entity": rel["target_entity"],
                    "rel_type": rel["relationship_type"],
                    "context": rel.get("context", "")[:200],
                },
            )

    except Exception as e:
        print(f"⚠️  Error storing relationships in graph: {e}")
        # Don't raise - we want ingestion to continue even if graph storage fails


def query_entity_relationships_graph(entity_name: str) -> list[dict]:
    """
    Query relationships for an entity from the graph

    Args:
        entity_name: Normalized name of the entity

    Returns:
        List of relationships with type and context
    """
    conn = get_kuzu_connection()

    try:
        # Get direct relationships
        result = conn.execute(
            """
            MATCH (e1:Entity {name: $entity_name})-[r:RELATES_TO]->(e2:Entity)
            RETURN e2.name, e2.type, r.type, r.context
            """,
            {"entity_name": entity_name},
        )

        relationships = []
        while result.has_next():
            row = result.get_next()
            relationships.append(
                {
                    "target_entity": row[0],
                    "target_type": row[1],
                    "relationship_type": row[2],
                    "context": row[3],
                }
            )

        return relationships

    except Exception as e:
        print(f"⚠️  Error querying entity relationships from graph: {e}")
        return []


def delete_chunk_from_graph(chunk_id: str) -> None:
    """
    Delete a chunk and its relationships from the graph

    Args:
        chunk_id: ID of the chunk to delete
    """
    conn = get_kuzu_connection()

    try:
        # Delete the chunk node (relationships will be deleted automatically)
        conn.execute(
            """
            MATCH (c:Chunk {id: $chunk_id})
            DETACH DELETE c
            """,
            {"chunk_id": chunk_id},
        )

    except Exception as e:
        print(f"⚠️  Error deleting chunk from graph: {e}")
