"""
Chat API endpoints (RAG)
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchAny
import anthropic
import aiosqlite

from core.config import settings
from core.logging_config import get_logger
from core.dependencies import get_current_user
from models.user import User
from services.embedding import embed_text

logger = get_logger(__name__)

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    num_context_chunks: int = 5


class ChatResponse(BaseModel):
    response: str
    sources: list[dict]


@router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Chat endpoint with RAG

    For MVP: Returns relevant context chunks.
    Phase 2: Integrate with LLM to generate responses.
    """
    # Get user's document IDs
    async with aiosqlite.connect(settings.sqlite_path) as db:
        async with db.execute(
            "SELECT id FROM documents WHERE user_id = ?",
            (current_user.id,)
        ) as cursor:
            user_doc_ids = [row[0] for row in await cursor.fetchall()]

    # Generate query embedding
    query_embedding = embed_text(request.message)

    # Search for relevant chunks (filtered by user's documents)
    qdrant = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)

    # Build filter for user's documents
    query_filter = None
    if user_doc_ids:
        query_filter = Filter(
            must=[
                FieldCondition(
                    key="document_id",
                    match=MatchAny(any=user_doc_ids)
                )
            ]
        )

    results = qdrant.search(
        collection_name="recall_chunks",
        query_vector=query_embedding,
        query_filter=query_filter,
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
async def chat_with_llm(
    request: ChatRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Chat with LLM integration using Claude

    Requires ANTHROPIC_API_KEY in .env
    """
    if not settings.anthropic_api_key:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY not configured. Please set it in .env file."
        )

    try:
        # Get user's document IDs
        async with aiosqlite.connect(settings.sqlite_path) as db:
            async with db.execute(
                "SELECT id FROM documents WHERE user_id = ?",
                (current_user.id,)
            ) as cursor:
                user_doc_ids = [row[0] for row in await cursor.fetchall()]

        # Generate query embedding
        query_embedding = embed_text(request.message)

        # Search for relevant chunks (filtered by user's documents)
        qdrant = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)

        # Build filter for user's documents
        query_filter = None
        if user_doc_ids:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchAny(any=user_doc_ids)
                    )
                ]
            )

        results = qdrant.search(
            collection_name="recall_chunks",
            query_vector=query_embedding,
            query_filter=query_filter,
            limit=request.num_context_chunks
        )

        # Format sources and build context
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
            context_texts.append(f"From '{source['document_title']}':\n{source['content']}")

        # Build prompt with context
        if not context_texts:
            context_section = "No relevant information found in the knowledge base."
        else:
            context_section = "\n\n---\n\n".join(context_texts)

        prompt = f"""You are a helpful AI assistant that answers questions based on the user's personal knowledge base.

Use the following context from the knowledge base to answer the user's question. If the context doesn't contain relevant information to answer the question, say so clearly.

Context from knowledge base:

{context_section}

---

User question: {request.message}

Please provide a helpful, accurate answer based on the context above. If you reference specific information, mention which document it came from."""

        # Call Claude API
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        message = client.messages.create(
            model=settings.llm_model,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = message.content[0].text

        return ChatResponse(
            response=response_text,
            sources=sources
        )

    except Exception as e:
        logger.error(f"LLM chat generation failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate response: {str(e)}"
        )
