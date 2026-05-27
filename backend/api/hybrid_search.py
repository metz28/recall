"""
Hybrid search API endpoint combining vector and graph retrieval
"""
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from core.config import settings
from services.hybrid_search import hybrid_search

router = APIRouter()


class HybridSearchResult(BaseModel):
    """Individual search result"""
    chunk_id: str
    score: float
    vector_score: float
    graph_score: float
    content: str
    document_id: str
    document_title: str
    chunk_index: int
    retrieval_source: str = Field(
        description="Source of retrieval: 'vector', 'graph', or 'hybrid'"
    )
    entities: list[str] = Field(default_factory=list)
    entity_overlap: Optional[int] = None


class HybridSearchResponse(BaseModel):
    """Hybrid search response"""
    results: list[HybridSearchResult]
    query: str
    total_results: int
    parameters: dict


@router.get("/", response_model=HybridSearchResponse)
async def search_hybrid(
    query: str = Query(..., description="Search query", min_length=1),
    limit: int = Query(
        default=10,
        ge=1,
        le=50,
        description="Number of results to return"
    ),
    alpha: float = Query(
        default=settings.hybrid_search_default_alpha,
        ge=0.0,
        le=1.0,
        description="Weight for vector score (0.0-1.0). Higher values favor semantic similarity over graph structure."
    ),
    graph_depth: int = Query(
        default=settings.hybrid_search_default_graph_depth,
        ge=0,
        le=settings.hybrid_search_max_graph_depth,
        description="Graph traversal depth in hops (0-3). 0 disables graph expansion."
    ),
    graph_expansion_limit: int = Query(
        default=settings.hybrid_search_default_expansion_limit,
        ge=0,
        le=settings.hybrid_search_max_expansion_limit,
        description="Maximum additional chunks to retrieve from graph"
    ),
    min_vector_score: float = Query(
        default=settings.hybrid_search_min_vector_score,
        ge=0.0,
        le=1.0,
        description="Minimum vector similarity score threshold"
    ),
    enable_entity_expansion: bool = Query(
        default=True,
        description="Enable entity-based graph expansion"
    ),
    collection: Optional[str] = Query(None, description="Filter by collection")
):
    """
    Hybrid search combining vector similarity and knowledge graph context

    This endpoint performs a two-stage retrieval:
    1. Vector search finds semantically similar chunks
    2. Graph enrichment adds context from related entities and relationships

    **Parameters:**
    - **alpha**: Controls the balance between vector and graph scores
      - 1.0 = pure vector search
      - 0.5 = equal weight to vector and graph
      - 0.0 = pure graph-based search
    - **graph_depth**: How many relationship hops to traverse
      - 0 = no graph expansion (vector search + entity overlap only)
      - 1 = direct relationships only
      - 2-3 = deeper graph traversal (may be slower)
    - **min_vector_score**: Filter out low-relevance vector results

    **Use cases:**
    - alpha=0.7 (default): Balanced search favoring semantic similarity
    - alpha=0.3: Structural search favoring entity relationships
    - graph_depth=0: Fast search without graph expansion
    - graph_depth=2-3: Comprehensive search finding distant connections

    Returns results ranked by hybrid score combining vector similarity and graph relevance.
    """
    try:
        results = await hybrid_search(
            query=query,
            limit=limit,
            alpha=alpha,
            graph_depth=graph_depth,
            graph_expansion_limit=graph_expansion_limit,
            min_vector_score=min_vector_score,
            enable_entity_expansion=enable_entity_expansion,
            collection=collection
        )

        # Convert to response model
        response_results = [
            HybridSearchResult(**result)
            for result in results
        ]

        return HybridSearchResponse(
            results=response_results,
            query=query,
            total_results=len(response_results),
            parameters={
                "limit": limit,
                "alpha": alpha,
                "graph_depth": graph_depth,
                "graph_expansion_limit": graph_expansion_limit,
                "min_vector_score": min_vector_score,
                "enable_entity_expansion": enable_entity_expansion,
                "collection": collection
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Hybrid search failed: {str(e)}"
        )
