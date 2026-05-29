"""
Search API endpoints
"""
from fastapi import APIRouter, Query
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny
from typing import Optional

from core.config import settings
from services.embedding import embed_text

router = APIRouter()


@router.get("/")
async def search(
    query: str = Query(..., description="Search query"),
    limit: int = Query(10, ge=1, le=50, description="Number of results"),
    collection: Optional[str] = Query(None, description="Filter by collection"),
    tags: Optional[str] = Query(None, description="Comma-separated tags (OR logic)")
):
    """
    Semantic search across all documents

    Returns the most relevant chunks based on vector similarity
    """
    # Generate query embedding
    query_embedding = embed_text(query)

    # Build query filter for collection and tags
    filter_conditions = []

    if collection:
        filter_conditions.append(
            FieldCondition(
                key="collection",
                match=MatchValue(value=collection)
            )
        )

    if tags:
        # Parse comma-separated tags and build OR filter (MatchAny)
        tag_list = [tag.strip() for tag in tags.split(',') if tag.strip()]
        if tag_list:
            filter_conditions.append(
                FieldCondition(
                    key="tags",
                    match=MatchAny(any=tag_list)
                )
            )

    # Combine filters with AND logic
    query_filter = None
    if filter_conditions:
        query_filter = Filter(must=filter_conditions)

    # Search in Qdrant
    qdrant = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    results = qdrant.search(
        collection_name="recall_chunks",
        query_vector=query_embedding,
        query_filter=query_filter,
        limit=limit
    )

    # Format results
    formatted_results = []
    for result in results:
        formatted_results.append({
            "chunk_id": result.id,
            "score": result.score,
            "content": result.payload.get("content"),
            "document_id": result.payload.get("document_id"),
            "document_title": result.payload.get("document_title"),
            "chunk_index": result.payload.get("chunk_index"),
            "collection": result.payload.get("collection"),
            "tags": result.payload.get("tags", [])
        })

    return formatted_results
