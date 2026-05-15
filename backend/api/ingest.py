"""
Document ingestion API endpoints
"""
from fastapi import APIRouter, UploadFile, File, HTTPException
from pathlib import Path
import aiosqlite
from uuid import uuid4
from datetime import datetime

from core.config import settings
from services.document_loader import load_document
from services.chunking import chunk_text
from services.embedding import embed_texts
from models.document import DocumentMetadata, Chunk
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

router = APIRouter()


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Upload and process a document

    Steps:
    1. Save file temporarily
    2. Extract text
    3. Chunk text
    4. Generate embeddings
    5. Store in Qdrant (vectors) and SQLite (metadata)
    """
    # Validate file type
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in settings.allowed_extensions_list:
        raise HTTPException(
            status_code=400,
            detail=f"File type {file_ext} not allowed. Allowed types: {settings.allowed_extensions}"
        )

    # Save file temporarily
    temp_dir = Path("./data/uploads")
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / f"{uuid4()}_{file.filename}"

    with open(temp_path, "wb") as f:
        content = await file.read()
        f.write(content)

    try:
        # Load document
        text_content, file_type = load_document(str(temp_path))

        # Create document metadata
        doc_id = str(uuid4())
        doc_metadata = DocumentMetadata(
            id=doc_id,
            title=file.filename,
            source_type="file",
            source_path=file.filename,
            file_type=file_type,
            file_size=len(content)
        )

        # Chunk text
        chunks = chunk_text(text_content)
        doc_metadata.num_chunks = len(chunks)

        # Generate embeddings
        embeddings = embed_texts(chunks)

        # Store in SQLite
        async with aiosqlite.connect(settings.sqlite_path) as db:
            await db.execute(
                """INSERT INTO documents
                   (id, title, source_type, source_path, file_type, file_size, num_chunks, collection, tags)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    doc_id,
                    doc_metadata.title,
                    doc_metadata.source_type,
                    doc_metadata.source_path,
                    doc_metadata.file_type,
                    doc_metadata.file_size,
                    doc_metadata.num_chunks,
                    doc_metadata.collection,
                    "[]"  # Empty tags for now
                )
            )

            # Store chunks in SQLite and prepare for Qdrant
            chunk_points = []
            for idx, (chunk_content, embedding) in enumerate(zip(chunks, embeddings)):
                chunk_id = str(uuid4())

                # Store in SQLite
                await db.execute(
                    """INSERT INTO chunks
                       (id, document_id, chunk_index, content)
                       VALUES (?, ?, ?, ?)""",
                    (chunk_id, doc_id, idx, chunk_content)
                )

                # Prepare Qdrant point
                chunk_points.append(
                    PointStruct(
                        id=chunk_id,
                        vector=embedding,
                        payload={
                            "document_id": doc_id,
                            "chunk_index": idx,
                            "content": chunk_content,
                            "document_title": doc_metadata.title
                        }
                    )
                )

            await db.commit()

        # Batch upload to Qdrant (outside the database context)
        qdrant = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
        qdrant.upsert(
            collection_name="recall_chunks",
            points=chunk_points
        )

        return {
            "status": "success",
            "document_id": doc_id,
            "title": doc_metadata.title,
            "num_chunks": len(chunks),
            "message": f"Document processed successfully with {len(chunks)} chunks"
        }

    finally:
        # Clean up temp file
        temp_path.unlink(missing_ok=True)


@router.get("/documents")
async def list_documents():
    """List all ingested documents"""
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM documents ORDER BY created_at DESC"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str):
    """Delete a document and all its chunks"""
    # Delete from SQLite
    async with aiosqlite.connect(settings.sqlite_path) as db:
        # Get chunk IDs first
        async with db.execute(
            "SELECT id FROM chunks WHERE document_id = ?", (document_id,)
        ) as cursor:
            chunk_ids = [row[0] for row in await cursor.fetchall()]

        # Delete chunks and document
        await db.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))
        await db.execute("DELETE FROM documents WHERE id = ?", (document_id,))
        await db.commit()

    # Delete from Qdrant
    qdrant = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    if chunk_ids:
        qdrant.delete(
            collection_name="recall_chunks",
            points_selector=chunk_ids
        )

    return {"status": "success", "message": f"Document {document_id} deleted"}
