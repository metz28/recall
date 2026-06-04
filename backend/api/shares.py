"""
API endpoints for shareable links
"""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional
import json
import aiosqlite

from models.share import (
    ShareCreate, ShareResponse, ShareList, ShareMetadata,
    SharedDocumentResponse, SharedSearchResponse
)
from models.user import User
from core.dependencies import get_current_user
from core.config import settings
from services import share_service
from services.embedding import embed_text
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

router = APIRouter()


# Protected endpoints (require authentication)

@router.post("/", response_model=ShareResponse, status_code=status.HTTP_201_CREATED)
async def create_share(
    share_data: ShareCreate,
    current_user: User = Depends(get_current_user)
):
    """
    Create a shareable link for a document, search, or collection.

    - **document**: Share a specific document by ID
    - **search**: Share search results with query parameters
    - **collection**: Share an entire collection
    """
    try:
        share = await share_service.create_share(current_user.id, share_data)
        return share
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create share: {str(e)}"
        )


@router.get("/", response_model=ShareList)
async def list_shares(current_user: User = Depends(get_current_user)):
    """List all shares created by the current user"""
    shares = await share_service.get_user_shares(current_user.id)
    return ShareList(shares=shares)


@router.delete("/{share_id}")
async def revoke_share(
    share_id: str,
    current_user: User = Depends(get_current_user)
):
    """Revoke (deactivate) a share link"""
    success = await share_service.revoke_share(current_user.id, share_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share not found or you don't have permission to revoke it"
        )
    return {"message": "Share revoked successfully"}


@router.delete("/{share_id}/permanent")
async def delete_share(
    share_id: str,
    current_user: User = Depends(get_current_user)
):
    """Permanently delete a share link"""
    success = await share_service.delete_share(current_user.id, share_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share not found or you don't have permission to delete it"
        )
    return {"message": "Share deleted successfully"}


# Public endpoints (no authentication required)

@router.get("/public/{token}/metadata", response_model=ShareMetadata)
async def get_share_metadata(token: str):
    """Get public metadata about a shared resource"""
    metadata = await share_service.get_share_metadata(token)
    if not metadata:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Share link not found"
        )
    return metadata


@router.get("/public/{token}/document", response_model=SharedDocumentResponse)
async def get_shared_document(token: str):
    """Access a shared document"""
    # Validate token
    is_valid, error_msg = await share_service.validate_share_token(token)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)

    # Get share info
    share = await share_service.get_share_by_token(token)
    if share['resource_type'] != 'document':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This is not a document share link"
        )

    # Increment view count
    await share_service.increment_view_count(token)

    # Get document info
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT id, title, file_type, num_chunks, created_at, tags, collection
            FROM documents
            WHERE id = ?
        """, (share['resource_id'],))
        doc = await cursor.fetchone()

        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )

        tags = json.loads(doc['tags']) if doc['tags'] else None

        return SharedDocumentResponse(
            id=doc['id'],
            title=doc['title'],
            file_type=doc['file_type'],
            num_chunks=doc['num_chunks'],
            created_at=doc['created_at'],
            tags=tags,
            collection=doc['collection']
        )


@router.get("/public/{token}/document/chunks")
async def get_shared_document_chunks(token: str, limit: int = 100):
    """Get chunks from a shared document"""
    # Validate token
    is_valid, error_msg = await share_service.validate_share_token(token)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)

    # Get share info
    share = await share_service.get_share_by_token(token)
    if share['resource_type'] != 'document':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This is not a document share link"
        )

    # Get document chunks
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT id, content, chunk_index
            FROM chunks
            WHERE document_id = ?
            ORDER BY chunk_index
            LIMIT ?
        """, (share['resource_id'], limit))
        chunks = await cursor.fetchall()

        return {
            "chunks": [
                {
                    "id": chunk['id'],
                    "content": chunk['content'],
                    "chunk_index": chunk['chunk_index']
                }
                for chunk in chunks
            ]
        }


@router.get("/public/{token}/search", response_model=SharedSearchResponse)
async def get_shared_search(token: str):
    """Execute a shared search query"""
    # Validate token
    is_valid, error_msg = await share_service.validate_share_token(token)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)

    # Get share info
    share = await share_service.get_share_by_token(token)
    if share['resource_type'] != 'search':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This is not a search share link"
        )

    # Increment view count
    await share_service.increment_view_count(token)

    # Parse search metadata
    metadata = json.loads(share['metadata']) if share['metadata'] else {}
    query = metadata.get('query', '')
    limit = metadata.get('limit', 10)
    collection = metadata.get('collection')
    tags = metadata.get('tags', [])

    # Get owner's user_id to scope the search
    owner_id = share['owner_id']

    # Perform the search (scoped to owner's documents)
    query_vector = embed_text(query)

    # Build Qdrant filter
    filter_conditions = [
        FieldCondition(key="user_id", match=MatchValue(value=owner_id))
    ]

    if collection:
        filter_conditions.append(
            FieldCondition(key="collection", match=MatchValue(value=collection))
        )

    if tags:
        filter_conditions.append(
            FieldCondition(key="tags", match=MatchValue(any=tags))
        )

    client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)

    search_results = client.search(
        collection_name="recall_chunks",
        query_vector=query_vector,
        limit=limit,
        query_filter=Filter(must=filter_conditions) if filter_conditions else None
    )

    results = []
    for result in search_results:
        results.append({
            "chunk_id": result.id,
            "document_id": result.payload.get("document_id"),
            "document_title": result.payload.get("document_title"),
            "content": result.payload.get("content"),
            "score": result.score,
            "chunk_index": result.payload.get("chunk_index")
        })

    return SharedSearchResponse(
        query=query,
        results=results,
        total_results=len(results),
        collection=collection,
        tags=tags
    )


@router.get("/public/{token}/collection")
async def get_shared_collection(token: str):
    """Get documents from a shared collection"""
    # Validate token
    is_valid, error_msg = await share_service.validate_share_token(token)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)

    # Get share info
    share = await share_service.get_share_by_token(token)
    if share['resource_type'] != 'collection':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This is not a collection share link"
        )

    # Increment view count
    await share_service.increment_view_count(token)

    # Get collection documents
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT id, title, file_type, num_chunks, created_at, tags
            FROM documents
            WHERE collection = ? AND user_id = ?
            ORDER BY created_at DESC
        """, (share['resource_id'], share['owner_id']))
        docs = await cursor.fetchall()

        return {
            "collection": share['resource_id'],
            "documents": [
                {
                    "id": doc['id'],
                    "title": doc['title'],
                    "file_type": doc['file_type'],
                    "num_chunks": doc['num_chunks'],
                    "created_at": doc['created_at'],
                    "tags": json.loads(doc['tags']) if doc['tags'] else None
                }
                for doc in docs
            ],
            "total": len(docs)
        }
