"""
Graph API endpoints for visualization
"""
import aiosqlite
from fastapi import APIRouter, Query, HTTPException
from typing import Optional

from core.config import settings

router = APIRouter()


@router.get("/full")
async def get_full_graph(
    limit: int = Query(100, ge=1, le=500, description="Maximum number of entities to return"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type (e.g., PERSON, ORG, GPE)"),
    min_mentions: int = Query(1, ge=1, description="Minimum number of mentions required")
):
    """
    Get the full knowledge graph with nodes (entities) and edges (relationships)

    Returns:
        - nodes: List of entities with metadata
        - edges: List of relationships between entities
        - stats: Graph statistics
    """
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row

        # Build query for entities
        entity_query = """
            SELECT id, name, entity_type, description, mention_count, variants
            FROM entities
            WHERE mention_count >= ?
        """
        params = [min_mentions]

        if entity_type:
            entity_query += " AND entity_type = ?"
            params.append(entity_type)

        entity_query += " ORDER BY mention_count DESC LIMIT ?"
        params.append(limit)

        # Fetch entities
        cursor = await db.execute(entity_query, params)
        entities = await cursor.fetchall()

        if not entities:
            return {
                "nodes": [],
                "edges": [],
                "stats": {
                    "total_nodes": 0,
                    "total_edges": 0,
                    "entity_types": {}
                }
            }

        # Convert to nodes format
        nodes = []
        entity_ids = set()
        entity_type_counts = {}

        for entity in entities:
            entity_id = entity["id"]
            entity_ids.add(entity_id)

            # Count entity types for stats
            etype = entity["entity_type"]
            entity_type_counts[etype] = entity_type_counts.get(etype, 0) + 1

            nodes.append({
                "id": entity_id,
                "label": entity["name"],
                "type": entity["entity_type"],
                "mention_count": entity["mention_count"],
                "description": entity["description"],
                "variants": entity["variants"]
            })

        # Fetch relationships between these entities
        if len(entity_ids) > 0:
            # Create placeholders for SQL IN clause
            placeholders = ','.join('?' * len(entity_ids))
            relationship_query = f"""
                SELECT id, source_entity_id, target_entity_id, relationship_type, context, confidence
                FROM relationships
                WHERE source_entity_id IN ({placeholders})
                  AND target_entity_id IN ({placeholders})
            """

            cursor = await db.execute(
                relationship_query,
                list(entity_ids) + list(entity_ids)
            )
            relationships = await cursor.fetchall()
        else:
            relationships = []

        # Convert to edges format
        edges = []
        for rel in relationships:
            edges.append({
                "id": rel["id"],
                "source": rel["source_entity_id"],
                "target": rel["target_entity_id"],
                "type": rel["relationship_type"],
                "context": rel["context"],
                "confidence": rel["confidence"]
            })

        return {
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "entity_types": entity_type_counts
            }
        }


@router.get("/subgraph/{entity_id}")
async def get_entity_subgraph(
    entity_id: str,
    depth: int = Query(1, ge=1, le=3, description="Number of relationship hops (1-3)"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of entities to return")
):
    """
    Get a subgraph centered on a specific entity

    Returns entities connected to the specified entity within the given depth,
    useful for exploring local neighborhoods in the knowledge graph.
    """
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row

        # Check if entity exists
        cursor = await db.execute(
            "SELECT id, name, entity_type, description, mention_count FROM entities WHERE id = ?",
            (entity_id,)
        )
        center_entity = await cursor.fetchone()

        if not center_entity:
            raise HTTPException(status_code=404, detail=f"Entity with id '{entity_id}' not found")

        # Start with the center entity
        entity_ids = {entity_id}
        all_entities = {entity_id: dict(center_entity)}
        all_relationships = []

        # Breadth-first expansion for specified depth
        current_layer = {entity_id}

        for hop in range(depth):
            if not current_layer or len(all_entities) >= limit:
                break

            # Find all relationships connected to current layer
            placeholders = ','.join('?' * len(current_layer))
            rel_query = f"""
                SELECT id, source_entity_id, target_entity_id, relationship_type, context, confidence
                FROM relationships
                WHERE source_entity_id IN ({placeholders})
                   OR target_entity_id IN ({placeholders})
            """

            cursor = await db.execute(rel_query, list(current_layer) + list(current_layer))
            relationships = await cursor.fetchall()

            # Collect new entity IDs for next layer
            next_layer = set()

            for rel in relationships:
                all_relationships.append(dict(rel))

                source_id = rel["source_entity_id"]
                target_id = rel["target_entity_id"]

                # Add new entities to next layer
                if source_id not in entity_ids:
                    next_layer.add(source_id)
                    entity_ids.add(source_id)

                if target_id not in entity_ids:
                    next_layer.add(target_id)
                    entity_ids.add(target_id)

                # Stop if we've hit the limit
                if len(entity_ids) >= limit:
                    break

            # Fetch entity details for next layer
            if next_layer and len(all_entities) < limit:
                remaining_limit = limit - len(all_entities)
                next_layer_list = list(next_layer)[:remaining_limit]

                placeholders = ','.join('?' * len(next_layer_list))
                entity_query = f"""
                    SELECT id, name, entity_type, description, mention_count
                    FROM entities
                    WHERE id IN ({placeholders})
                """

                cursor = await db.execute(entity_query, next_layer_list)
                new_entities = await cursor.fetchall()

                for entity in new_entities:
                    all_entities[entity["id"]] = dict(entity)

            current_layer = next_layer

        # Format nodes
        nodes = []
        entity_type_counts = {}

        for entity_id, entity_data in all_entities.items():
            etype = entity_data["entity_type"]
            entity_type_counts[etype] = entity_type_counts.get(etype, 0) + 1

            nodes.append({
                "id": entity_id,
                "label": entity_data["name"],
                "type": entity_data["entity_type"],
                "mention_count": entity_data["mention_count"],
                "description": entity_data.get("description")
            })

        # Format edges (only include edges between entities in the subgraph)
        edges = []
        for rel in all_relationships:
            if rel["source_entity_id"] in entity_ids and rel["target_entity_id"] in entity_ids:
                edges.append({
                    "id": rel["id"],
                    "source": rel["source_entity_id"],
                    "target": rel["target_entity_id"],
                    "type": rel["relationship_type"],
                    "context": rel["context"],
                    "confidence": rel["confidence"]
                })

        return {
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "entity_types": entity_type_counts,
                "center_entity_id": entity_id,
                "depth": depth
            }
        }


@router.get("/entity/{entity_id}")
async def get_entity_detail(entity_id: str):
    """
    Get detailed information about a specific entity

    Returns:
        - Entity metadata (id, name, type, description, mention_count)
        - All relationships (both outgoing and incoming)
        - Sample mentions with context
    """
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row

        # Fetch entity
        cursor = await db.execute(
            "SELECT id, name, entity_type, description, mention_count, variants, created_at FROM entities WHERE id = ?",
            (entity_id,)
        )
        entity = await cursor.fetchone()

        if not entity:
            raise HTTPException(status_code=404, detail=f"Entity with id '{entity_id}' not found")

        # Fetch relationships (outgoing and incoming)
        cursor = await db.execute("""
            SELECT
                r.id,
                r.source_entity_id,
                r.target_entity_id,
                r.relationship_type,
                r.context,
                r.confidence,
                e_source.name as source_name,
                e_source.entity_type as source_type,
                e_target.name as target_name,
                e_target.entity_type as target_type
            FROM relationships r
            LEFT JOIN entities e_source ON r.source_entity_id = e_source.id
            LEFT JOIN entities e_target ON r.target_entity_id = e_target.id
            WHERE r.source_entity_id = ? OR r.target_entity_id = ?
            ORDER BY r.confidence DESC
        """, (entity_id, entity_id))

        relationships = await cursor.fetchall()

        # Format relationships
        formatted_relationships = []
        for rel in relationships:
            # Determine if this entity is source or target
            is_source = rel["source_entity_id"] == entity_id

            formatted_relationships.append({
                "id": rel["id"],
                "relationship_type": rel["relationship_type"],
                "direction": "outgoing" if is_source else "incoming",
                "other_entity": {
                    "id": rel["target_entity_id"] if is_source else rel["source_entity_id"],
                    "name": rel["target_name"] if is_source else rel["source_name"],
                    "type": rel["target_type"] if is_source else rel["source_type"]
                },
                "context": rel["context"],
                "confidence": rel["confidence"]
            })

        # Fetch sample mentions (limit to 5 for performance)
        cursor = await db.execute("""
            SELECT em.context, c.content, d.title as document_title
            FROM entity_mentions em
            LEFT JOIN chunks c ON em.chunk_id = c.id
            LEFT JOIN documents d ON c.document_id = d.id
            WHERE em.entity_id = ?
            ORDER BY em.id
            LIMIT 5
        """, (entity_id,))

        mentions = await cursor.fetchall()

        formatted_mentions = [
            {
                "context": mention["context"],
                "document_title": mention["document_title"]
            }
            for mention in mentions
        ]

        return {
            "id": entity["id"],
            "name": entity["name"],
            "entity_type": entity["entity_type"],
            "description": entity["description"],
            "mention_count": entity["mention_count"],
            "variants": entity["variants"],
            "created_at": entity["created_at"],
            "relationships": formatted_relationships,
            "sample_mentions": formatted_mentions
        }
