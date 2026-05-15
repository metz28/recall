"""
Search API endpoints
"""
from fastapi import APIRouter, Query
from qdrant_client import QdrantClient

from core.config import settings
from services.embedding import embed_text

router = APIRouter()


@router.get("/")
async def search(
    query: str = Query(..., description="Search query"),
    limit: int = Query(10, ge=1, le=50, description="Number of results")
):
    """
    Semantic search across all documents

    Returns the most relevant chunks based on vector similarity
    """
    # Generate query embedding
    query_embedding = embed_text(query)

    # Search in Qdrant
    qdrant = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    results = qdrant.search(
        collection_name="recall_chunks",
        query_vector=query_embedding,
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
            "chunk_index": result.payload.get("chunk_index")
        })

    return {
        "query": query,
        "results": formatted_results,
        "count": len(formatted_results)
    }
