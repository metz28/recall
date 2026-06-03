"""
Service for exporting and importing knowledge base data
"""
import json
import uuid
from datetime import datetime
from typing import Optional
import aiosqlite
from qdrant_client import QdrantClient

from core.config import settings
from core.logging_config import get_logger
from models.export_import import DocumentExport, ExportRequest, ImportRequest
from services.embedding import EmbeddingService
from services.chunking import chunk_text

logger = get_logger(__name__)


async def export_document(
    user_id: str,
    document_id: str,
    include_embeddings: bool = False,
    include_graph: bool = True
) -> Optional[DocumentExport]:
    """Export a single document with all its data"""
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row

        # Get document metadata
        cursor = await db.execute("""
            SELECT id, title, source_type, source_path, file_type, file_size,
                   num_chunks, created_at, updated_at, collection, tags
            FROM documents
            WHERE id = ? AND user_id = ?
        """, (document_id, user_id))
        doc_row = await cursor.fetchone()

        if not doc_row:
            return None

        doc = dict(doc_row)
        tags = json.loads(doc['tags']) if doc['tags'] else None

        # Get all chunks
        cursor = await db.execute("""
            SELECT id, content, chunk_index
            FROM chunks
            WHERE document_id = ?
            ORDER BY chunk_index
        """, (document_id,))
        chunks = [dict(row) for row in await cursor.fetchall()]

        # Get embeddings if requested
        if include_embeddings:
            client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
            for chunk in chunks:
                try:
                    point = client.retrieve(
                        collection_name="recall_chunks",
                        ids=[chunk['id']]
                    )
                    if point:
                        chunk['embedding'] = point[0].vector
                except Exception as e:
                    logger.warning(f"Could not retrieve embedding for chunk {chunk['id']}: {e}")

        # Get entities and relationships if requested
        entities = []
        relationships = []

        if include_graph:
            # Get entities mentioned in this document's chunks
            chunk_ids = [c['id'] for c in chunks]
            if chunk_ids:
                placeholders = ','.join('?' * len(chunk_ids))
                cursor = await db.execute(f"""
                    SELECT DISTINCT e.id, e.name, e.entity_type, e.description, e.mention_count, e.variants
                    FROM entities e
                    JOIN entity_mentions em ON e.id = em.entity_id
                    WHERE em.chunk_id IN ({placeholders})
                """, chunk_ids)
                entities = [dict(row) for row in await cursor.fetchall()]

                # Get relationships between these entities
                if entities:
                    entity_ids = [e['id'] for e in entities]
                    placeholders = ','.join('?' * len(entity_ids))
                    cursor = await db.execute(f"""
                        SELECT r.id, r.source_entity_id, r.target_entity_id,
                               r.relationship_type, r.context, r.confidence
                        FROM relationships r
                        WHERE r.source_entity_id IN ({placeholders})
                           OR r.target_entity_id IN ({placeholders})
                    """, entity_ids + entity_ids)
                    relationships = [dict(row) for row in await cursor.fetchall()]

        return DocumentExport(
            id=doc['id'],
            title=doc['title'],
            source_type=doc['source_type'],
            source_path=doc['source_path'],
            file_type=doc['file_type'],
            file_size=doc['file_size'],
            num_chunks=doc['num_chunks'],
            created_at=datetime.fromisoformat(doc['created_at']),
            updated_at=datetime.fromisoformat(doc['updated_at']),
            collection=doc['collection'],
            tags=tags,
            chunks=chunks,
            entities=entities if include_graph else None,
            relationships=relationships if include_graph else None
        )


async def export_collection(
    user_id: str,
    collection_name: str,
    include_embeddings: bool = False,
    include_graph: bool = True
) -> list[DocumentExport]:
    """Export all documents in a collection"""
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT id FROM documents
            WHERE collection = ? AND user_id = ?
        """, (collection_name, user_id))
        doc_ids = [row['id'] for row in await cursor.fetchall()]

    documents = []
    for doc_id in doc_ids:
        doc = await export_document(user_id, doc_id, include_embeddings, include_graph)
        if doc:
            documents.append(doc)

    return documents


async def export_all(
    user_id: str,
    include_embeddings: bool = False,
    include_graph: bool = True
) -> list[DocumentExport]:
    """Export all documents for a user"""
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT id FROM documents WHERE user_id = ?
        """, (user_id,))
        doc_ids = [row['id'] for row in await cursor.fetchall()]

    documents = []
    for doc_id in doc_ids:
        doc = await export_document(user_id, doc_id, include_embeddings, include_graph)
        if doc:
            documents.append(doc)

    return documents


async def import_documents(
    user_id: str,
    documents: list[dict],
    import_mode: str = "skip",
    regenerate_embeddings: bool = True,
    target_collection: Optional[str] = None
) -> dict:
    """
    Import documents from exported data

    Returns dict with statistics: imported, skipped, replaced, errors
    """
    stats = {
        "imported": 0,
        "skipped": 0,
        "replaced": 0,
        "errors": [],
        "total_chunks": 0,
        "total_entities": 0,
        "total_relationships": 0
    }

    embedding_service = EmbeddingService() if regenerate_embeddings else None
    client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port) if regenerate_embeddings else None

    for doc_data in documents:
        try:
            doc_id = doc_data.get('id', str(uuid.uuid4()))

            # Check if document exists
            async with aiosqlite.connect(settings.sqlite_path) as db:
                cursor = await db.execute(
                    "SELECT id FROM documents WHERE id = ? AND user_id = ?",
                    (doc_id, user_id)
                )
                exists = await cursor.fetchone()

                if exists:
                    if import_mode == "skip":
                        stats["skipped"] += 1
                        continue
                    elif import_mode == "replace":
                        # Delete existing document
                        await db.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
                        await db.execute("DELETE FROM chunks WHERE document_id = ?", (doc_id,))
                        await db.commit()
                        stats["replaced"] += 1
                    # merge mode: just add to existing

                # Use target_collection if provided, otherwise use original
                collection = target_collection or doc_data.get('collection')
                tags = doc_data.get('tags', [])

                # Insert document
                await db.execute("""
                    INSERT INTO documents (
                        id, title, source_type, source_path, file_type, file_size,
                        num_chunks, created_at, updated_at, collection, tags, user_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    doc_id,
                    doc_data['title'],
                    doc_data.get('source_type', 'import'),
                    doc_data.get('source_path'),
                    doc_data.get('file_type'),
                    doc_data.get('file_size'),
                    len(doc_data.get('chunks', [])),
                    doc_data.get('created_at', datetime.utcnow().isoformat()),
                    datetime.utcnow().isoformat(),
                    collection,
                    json.dumps(tags) if tags else None,
                    user_id
                ))

                # Insert chunks
                chunks = doc_data.get('chunks', [])
                for chunk_data in chunks:
                    chunk_id = chunk_data.get('id', str(uuid.uuid4()))
                    content = chunk_data['content']
                    chunk_index = chunk_data.get('chunk_index', 0)

                    await db.execute("""
                        INSERT INTO chunks (id, document_id, chunk_index, content)
                        VALUES (?, ?, ?, ?)
                    """, (chunk_id, doc_id, chunk_index, content))

                    # Generate and store embeddings if requested
                    if regenerate_embeddings and embedding_service and client:
                        try:
                            embedding = embedding_service.embed_text(content)

                            client.upsert(
                                collection_name="recall_chunks",
                                points=[{
                                    "id": chunk_id,
                                    "vector": embedding,
                                    "payload": {
                                        "document_id": doc_id,
                                        "document_title": doc_data['title'],
                                        "content": content,
                                        "chunk_index": chunk_index,
                                        "collection": collection,
                                        "tags": tags,
                                        "user_id": user_id
                                    }
                                }]
                            )
                        except Exception as e:
                            logger.warning(f"Failed to generate embedding for chunk {chunk_id}: {e}")

                    stats["total_chunks"] += 1

                # Import entities if included
                entities = doc_data.get('entities', [])
                if entities:
                    entity_id_map = {}  # Map old IDs to new IDs

                    for entity_data in entities:
                        old_entity_id = entity_data.get('id')

                        # Check if entity already exists by name
                        cursor = await db.execute(
                            "SELECT id FROM entities WHERE name = ? AND entity_type = ?",
                            (entity_data['name'], entity_data['entity_type'])
                        )
                        existing = await cursor.fetchone()

                        if existing:
                            entity_id_map[old_entity_id] = existing[0]
                        else:
                            new_entity_id = str(uuid.uuid4())
                            entity_id_map[old_entity_id] = new_entity_id

                            await db.execute("""
                                INSERT INTO entities (id, name, entity_type, description, mention_count, variants)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """, (
                                new_entity_id,
                                entity_data['name'],
                                entity_data['entity_type'],
                                entity_data.get('description'),
                                entity_data.get('mention_count', 1),
                                entity_data.get('variants')
                            ))
                            stats["total_entities"] += 1

                # Import relationships if included
                relationships = doc_data.get('relationships', [])
                if relationships:
                    for rel_data in relationships:
                        source_id = entity_id_map.get(rel_data['source_entity_id'])
                        target_id = entity_id_map.get(rel_data['target_entity_id'])

                        if source_id and target_id:
                            rel_id = str(uuid.uuid4())
                            await db.execute("""
                                INSERT INTO relationships (
                                    id, source_entity_id, target_entity_id,
                                    relationship_type, context, confidence
                                ) VALUES (?, ?, ?, ?, ?, ?)
                            """, (
                                rel_id,
                                source_id,
                                target_id,
                                rel_data['relationship_type'],
                                rel_data.get('context'),
                                rel_data.get('confidence', 1.0)
                            ))
                            stats["total_relationships"] += 1

                await db.commit()
                stats["imported"] += 1
                logger.info(f"Imported document: {doc_data['title']}")

        except Exception as e:
            error_msg = f"Failed to import document {doc_data.get('title', 'unknown')}: {str(e)}"
            logger.error(error_msg)
            stats["errors"].append(error_msg)

    return stats
