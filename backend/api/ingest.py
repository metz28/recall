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
from services.entity_extraction import (
    extract_entities_batch,
    deduplicate_entities,
)
from services.llm_entity_extraction import extract_entities_batch_llm
from services.graph_service import store_entities_in_graph
from models.document import DocumentMetadata, Chunk
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct
import json

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

        # Extract entities from chunks (if enabled)
        all_entity_mentions = []
        if settings.entity_extraction_enabled:
            try:
                extraction_method = settings.entity_extraction_method.lower()
                print(
                    f"🔍 Extracting entities from {len(chunks)} chunks using {extraction_method}..."
                )

                if extraction_method == "llm":
                    chunk_entities = extract_entities_batch_llm(
                        chunks,
                        entity_types=settings.entity_types_set,
                        model_name=settings.llm_model,
                        context_window=settings.entity_context_window,
                    )
                else:  # default to spacy
                    chunk_entities = extract_entities_batch(
                        chunks,
                        entity_types=settings.entity_types_set,
                        model_name=settings.spacy_model,
                        context_window=settings.entity_context_window,
                    )

                # Flatten all mentions for deduplication
                for chunk_idx, entities in enumerate(chunk_entities):
                    for entity in entities:
                        entity["chunk_index"] = chunk_idx
                        all_entity_mentions.append(entity)
                print(f"✅ Extracted {len(all_entity_mentions)} entity mentions")
            except Exception as e:
                print(f"⚠️  Entity extraction failed: {e}")
                # Continue with ingestion even if entity extraction fails

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
            chunk_id_map = {}  # Map chunk_index -> chunk_id
            for idx, (chunk_content, embedding) in enumerate(zip(chunks, embeddings)):
                chunk_id = str(uuid4())
                chunk_id_map[idx] = chunk_id

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

            # Store entities if extracted
            if all_entity_mentions and settings.entity_extraction_enabled:
                try:
                    # Deduplicate entities
                    entities_map = deduplicate_entities(all_entity_mentions)
                    print(f"📊 Found {len(entities_map)} unique entities")

                    # Store unique entities
                    entity_id_map = {}  # Map normalized_name -> entity_id
                    for norm_name, entity_data in entities_map.items():
                        entity_id = str(uuid4())
                        entity_id_map[norm_name] = entity_id

                        await db.execute(
                            """INSERT OR REPLACE INTO entities
                               (id, name, entity_type, mention_count, variants)
                               VALUES (?, ?, ?, ?, ?)""",
                            (
                                entity_id,
                                entity_data['canonical_name'],
                                entity_data['type'],
                                entity_data['mention_count'],
                                json.dumps(entity_data['variants'])
                            )
                        )

                    # Store entity mentions
                    for mention in all_entity_mentions:
                        chunk_idx = mention['chunk_index']
                        chunk_id = chunk_id_map[chunk_idx]
                        entity_id = entity_id_map[mention['normalized_name']]

                        mention_id = str(uuid4())
                        await db.execute(
                            """INSERT INTO entity_mentions
                               (id, entity_id, chunk_id, context, position)
                               VALUES (?, ?, ?, ?, ?)""",
                            (
                                mention_id,
                                entity_id,
                                chunk_id,
                                mention.get('context', ''),
                                mention.get('start', 0)
                            )
                        )

                    # Store in Kuzu graph
                    for chunk_idx, chunk_entities in enumerate(
                        extract_entities_batch(
                            chunks,
                            entity_types=settings.entity_types_set,
                            model_name=settings.spacy_model
                        )
                    ):
                        if chunk_entities:
                            chunk_id = chunk_id_map[chunk_idx]
                            store_entities_in_graph(
                                chunk_entities,
                                chunk_id,
                                chunks[chunk_idx]
                            )

                    print(f"✅ Stored entities in database and graph")
                except Exception as e:
                    print(f"⚠️  Entity storage failed: {e}")
                    # Continue with ingestion

            await db.commit()

        # Batch upload to Qdrant (outside the database context)
        qdrant = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
        qdrant.upsert(
            collection_name="recall_chunks",
            points=chunk_points
        )

        # Prepare response
        response = {
            "status": "success",
            "document_id": doc_id,
            "title": doc_metadata.title,
            "num_chunks": len(chunks),
            "message": f"Document processed successfully with {len(chunks)} chunks"
        }

        # Add entity info if available
        if all_entity_mentions and settings.entity_extraction_enabled:
            entities_map = deduplicate_entities(all_entity_mentions)
            response["num_entities"] = len(entities_map)
            response["num_entity_mentions"] = len(all_entity_mentions)

        return response

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
