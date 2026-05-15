"""
Chat API endpoints (RAG)
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from qdrant_client import QdrantClient

from core.config import settings
from services.embedding import embed_text

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    num_context_chunks: int = 5


class ChatResponse(BaseModel):
    response: str
    sources: list[dict]


@router.post("/", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Chat endpoint with RAG

    For MVP: Returns relevant context chunks.
    Phase 2: Integrate with LLM to generate responses.
    """
    # Generate query embedding
    query_embedding = embed_text(request.message)

    # Search for relevant chunks
    qdrant = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    results = qdrant.search(
        collection_name="recall_chunks",
        query_vector=query_embedding,
        limit=request.num_context_chunks
    )

    # Format sources
    sources = []
    context_texts = []
    for result in results:
        source = {
            "chunk_id": result.id,
            "score": result.score,
            "content": result.payload.get("content"),
            "document_title": result.payload.get("document_title")
        }
        sources.append(source)
        context_texts.append(result.payload.get("content"))

    # For MVP: Just return context. Phase 2: Generate response with LLM
    if not sources:
        response_text = "I couldn't find any relevant information in your knowledge base."
    else:
        # Simple response for MVP
        response_text = f"I found {len(sources)} relevant passages:\n\n"
        for idx, source in enumerate(sources, 1):
            response_text += f"{idx}. From '{source['document_title']}': {source['content'][:200]}...\n\n"

    return ChatResponse(
        response=response_text,
        sources=sources
    )


@router.post("/generate")
async def chat_with_llm(request: ChatRequest):
    """
    Chat with LLM integration (Phase 2)

    Requires OPENAI_API_KEY or ANTHROPIC_API_KEY in .env
    """
    # TODO: Implement LLM integration
    raise HTTPException(
        status_code=501,
        detail="LLM integration not yet implemented. Use the basic /chat endpoint for MVP."
    )
