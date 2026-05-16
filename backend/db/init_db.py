"""
Database initialization
"""
import aiosqlite
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from core.config import settings


async def init_sqlite():
    """Initialize SQLite database with schema"""
    db_path = Path(settings.sqlite_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(settings.sqlite_path) as db:
        # Documents table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_path TEXT,
                file_type TEXT,
                file_size INTEGER,
                num_chunks INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                collection TEXT,
                tags TEXT  -- JSON array as string
            )
        """)

        # Chunks table (for quick lookup)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                start_char INTEGER,
                end_char INTEGER,
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
            )
        """)

        # Entities table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                description TEXT,
                mention_count INTEGER DEFAULT 1,
                variants TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Entity mentions table (links entities to chunks)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS entity_mentions (
                id TEXT PRIMARY KEY,
                entity_id TEXT NOT NULL,
                chunk_id TEXT NOT NULL,
                context TEXT,
                position INTEGER,
                FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE,
                FOREIGN KEY (chunk_id) REFERENCES chunks(id) ON DELETE CASCADE
            )
        """)

        # Create indices for performance
        await db.execute("CREATE INDEX IF NOT EXISTS idx_entity_mentions_entity ON entity_mentions(entity_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_entity_mentions_chunk ON entity_mentions(chunk_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id)")

        await db.commit()
        print("✅ SQLite initialized")


async def init_qdrant():
    """Initialize Qdrant collection"""
    client = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)

    collection_name = "recall_chunks"

    # Check if collection exists
    collections = client.get_collections().collections
    if collection_name not in [c.name for c in collections]:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=settings.embedding_dimension,
                distance=Distance.COSINE
            )
        )
        print(f"✅ Qdrant collection '{collection_name}' created")
    else:
        print(f"✅ Qdrant collection '{collection_name}' already exists")


async def init_kuzu():
    """Initialize Kuzu graph database (Phase 2)"""
    import kuzu

    db_path = Path(settings.kuzu_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    db = kuzu.Database(settings.kuzu_path)
    conn = kuzu.Connection(db)

    # Create node tables
    try:
        conn.execute("CREATE NODE TABLE IF NOT EXISTS Entity(name STRING, type STRING, description STRING, PRIMARY KEY(name))")
        conn.execute("CREATE NODE TABLE IF NOT EXISTS Chunk(id STRING, content STRING, PRIMARY KEY(id))")

        # Create relationship tables
        conn.execute("CREATE REL TABLE IF NOT EXISTS MENTIONED_IN(FROM Entity TO Chunk, context STRING)")
        conn.execute("CREATE REL TABLE IF NOT EXISTS RELATES_TO(FROM Entity TO Entity, type STRING, context STRING)")

        print("✅ Kuzu graph initialized")
    except Exception as e:
        # Tables might already exist
        print(f"✅ Kuzu graph already initialized ({e})")


async def init_databases():
    """Initialize all databases"""
    await init_sqlite()
    await init_qdrant()
    await init_kuzu()
