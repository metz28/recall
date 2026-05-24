"""
Hybrid search service combining vector and graph retrieval
"""
from typing import Optional
from qdrant_client import QdrantClient

from core.config import settings
from services.embedding import embed_text
from services.entity_extraction import extract_entities_from_text
from services.graph_retrieval import (
    get_chunk_entities,
    get_chunks_by_entities,
    get_related_entities,
    calculate_entity_overlap
)


async def hybrid_search(
    query: str,
    limit: int = 10,
    alpha: float = 0.7,
    graph_depth: int = 1,
    graph_expansion_limit: int = 5,
    min_vector_score: float = 0.3,
    enable_entity_expansion: bool = True
) -> list[dict]:
    """
    Perform hybrid search combining vector similarity and graph context

    Args:
        query: Search query
        limit: Number of final results to return
        alpha: Weight for vector score (0.0-1.0). Final score = alpha * vector + (1-alpha) * graph
        graph_depth: Graph traversal depth for entity expansion (0-3 hops)
        graph_expansion_limit: Maximum additional chunks to retrieve from graph
        min_vector_score: Minimum vector similarity score threshold
        enable_entity_expansion: Whether to expand search via related entities

    Returns:
        List of result dictionaries sorted by hybrid score
    """
    # Step 1: Extract entities from query
    query_entities = []
    if enable_entity_expansion or alpha < 1.0:
        try:
            extracted = extract_entities_from_text(
                query,
                entity_types=settings.entity_types_set,
                model_name=settings.spacy_model
            )
            query_entities = [e["normalized_name"] for e in extracted]
        except Exception as e:
            print(f"⚠️  Entity extraction from query failed: {e}")

    # Step 2: Perform vector search (get more candidates for filtering)
    query_embedding = embed_text(query)
    qdrant = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)

    vector_results = qdrant.search(
        collection_name="recall_chunks",
        query_vector=query_embedding,
        limit=limit * 2  # Get extra candidates
    )

    # Step 3: Filter by min_vector_score and enrich with graph context
    enriched_results = []

    for result in vector_results:
        if result.score < min_vector_score:
            continue

        chunk_id = str(result.id)

        # Get entities mentioned in this chunk
        try:
            chunk_entities = await get_chunk_entities(chunk_id)
        except Exception as e:
            print(f"⚠️  Failed to get chunk entities: {e}")
            chunk_entities = []

        # Calculate graph score based on entity overlap
        entity_overlap = await calculate_entity_overlap(chunk_entities, query_entities)

        # Graph score: normalize by max possible overlap
        max_overlap = max(len(query_entities), 1)
        graph_score = entity_overlap / max_overlap if query_entities else 0.0

        # Fuse scores
        hybrid_score = alpha * result.score + (1 - alpha) * graph_score

        enriched_results.append({
            "chunk_id": chunk_id,
            "score": hybrid_score,
            "vector_score": result.score,
            "graph_score": graph_score,
            "content": result.payload.get("content"),
            "document_id": result.payload.get("document_id"),
            "document_title": result.payload.get("document_title"),
            "chunk_index": result.payload.get("chunk_index"),
            "retrieval_source": "vector",
            "entities": chunk_entities,
            "entity_overlap": entity_overlap
        })

    # Step 4: Entity expansion - find additional chunks via graph traversal
    graph_chunks = []

    if enable_entity_expansion and graph_depth > 0 and query_entities:
        try:
            # Get related entities
            related = await get_related_entities(
                query_entities,
                depth=graph_depth,
                limit_per_entity=5
            )

            # Extract unique related entity names
            related_entity_names = list(set(r["related_entity"] for r in related))

            # Get chunks mentioning related entities
            existing_chunk_ids = {r["chunk_id"] for r in enriched_results}

            graph_chunks = await get_chunks_by_entities(
                related_entity_names,
                limit=graph_expansion_limit,
                exclude_chunk_ids=existing_chunk_ids
            )

            # Score graph-retrieved chunks
            for chunk in graph_chunks:
                chunk_id = chunk["id"]

                # Get entities in this chunk
                try:
                    chunk_entities = await get_chunk_entities(chunk_id)
                except Exception as e:
                    chunk_entities = []

                # Calculate entity overlap
                entity_overlap = await calculate_entity_overlap(chunk_entities, query_entities)

                # For graph-only results, vector_score is 0, graph_score is based on overlap
                graph_score = entity_overlap / max_overlap if query_entities else 0.5

                # Boost graph score for graph-retrieved items
                graph_score = min(graph_score * 1.2, 1.0)

                hybrid_score = alpha * 0.0 + (1 - alpha) * graph_score

                enriched_results.append({
                    "chunk_id": chunk_id,
                    "score": hybrid_score,
                    "vector_score": 0.0,
                    "graph_score": graph_score,
                    "content": chunk["content"],
                    "document_id": chunk["document_id"],
                    "document_title": chunk["document_title"],
                    "chunk_index": chunk["chunk_index"],
                    "retrieval_source": "graph",
                    "entities": chunk_entities,
                    "entity_overlap": entity_overlap
                })

        except Exception as e:
            print(f"⚠️  Entity expansion failed: {e}")

    # Step 5: Deduplicate and rank
    final_results = deduplicate_and_rank(enriched_results, limit)

    return final_results


def deduplicate_and_rank(results: list[dict], limit: int) -> list[dict]:
    """
    Remove duplicate chunks and return top-ranked results

    Args:
        results: List of result dictionaries
        limit: Maximum number of results to return

    Returns:
        Deduplicated and sorted results
    """
    # Deduplicate by chunk_id, keeping highest score
    seen_chunks = {}

    for result in results:
        chunk_id = result["chunk_id"]
        if chunk_id not in seen_chunks or result["score"] > seen_chunks[chunk_id]["score"]:
            seen_chunks[chunk_id] = result

    # Sort by score and limit
    sorted_results = sorted(seen_chunks.values(), key=lambda x: x["score"], reverse=True)

    return sorted_results[:limit]


def calculate_graph_score(
    entity_overlap: int,
    graph_distance: Optional[int],
    max_overlap: int
) -> float:
    """
    Calculate graph-based relevance score

    Args:
        entity_overlap: Number of common entities between chunk and query
        graph_distance: Shortest path distance in graph (None if not connected)
        max_overlap: Maximum possible entity overlap (for normalization)

    Returns:
        Graph score between 0.0 and 1.0
    """
    # Base score from entity overlap
    overlap_score = entity_overlap / max(max_overlap, 1)

    # Bonus from graph connectivity
    distance_score = 0.0
    if graph_distance is not None:
        # Closer entities get higher scores
        # distance=1 -> 0.3, distance=2 -> 0.2, distance=3 -> 0.1
        distance_score = max(0.0, 0.4 - (graph_distance * 0.1))

    # Combine scores (weighted average)
    graph_score = 0.7 * overlap_score + 0.3 * distance_score

    return min(graph_score, 1.0)


def fuse_scores(
    vector_score: float,
    graph_score: float,
    alpha: float
) -> float:
    """
    Combine vector and graph scores using weighted average

    Args:
        vector_score: Semantic similarity score from vector search
        graph_score: Structural relevance score from graph
        alpha: Weight for vector score (0.0-1.0)

    Returns:
        Fused score
    """
    return alpha * vector_score + (1 - alpha) * graph_score
