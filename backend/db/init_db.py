"""
Database initialization
"""
import aiosqlite
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from core.config import settings
from core.logging_config import get_logger

logger = get_logger(__name__)


async def migrate_collections():
    """Migrate existing documents to use default collection"""
    async with aiosqlite.connect(settings.sqlite_path) as db:
        # Update NULL collections to "default"
        await db.execute("""
            UPDATE documents
            SET collection = 'default'
            WHERE collection IS NULL
        """)
        rows_updated = db.total_changes
        await db.commit()

        if rows_updated > 0:
            logger.info(f"Migrated {rows_updated} documents to 'default' collection")


async def migrate_add_users():
    """Migrate database to add users and user_id to documents"""
    import uuid

    async with aiosqlite.connect(settings.sqlite_path) as db:
        # Check if users table exists
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
        )
        users_table_exists = await cursor.fetchone() is not None

        if not users_table_exists:
            logger.info("Users table doesn't exist yet, skipping user migration")
            return

        # Check if user_id column exists in documents
        cursor = await db.execute("PRAGMA table_info(documents)")
        existing_columns = {row[1] for row in await cursor.fetchall()}

        if 'user_id' in existing_columns:
            logger.info("user_id column already exists in documents table")
            return

        # Add user_id column to documents
        await db.execute("ALTER TABLE documents ADD COLUMN user_id TEXT")
        logger.info("Added user_id column to documents table")

        # Create index on user_id
        await db.execute("CREATE INDEX IF NOT EXISTS idx_documents_user ON documents(user_id)")
        logger.info("Created index on documents(user_id)")

        # Check if there are any existing documents without user_id
        cursor = await db.execute("SELECT COUNT(*) FROM documents WHERE user_id IS NULL")
        count = (await cursor.fetchone())[0]

        if count > 0:
            # Create a system user for existing documents
            system_user_id = str(uuid.uuid4())
            from core.security import hash_password

            await db.execute("""
                INSERT INTO users (id, email, username, hashed_password, is_active)
                VALUES (?, ?, ?, ?, ?)
            """, (system_user_id, "system@recall.local", "system", hash_password("SYSTEM_NO_LOGIN"), 0))

            # Assign all existing documents to system user
            await db.execute("""
                UPDATE documents
                SET user_id = ?
                WHERE user_id IS NULL
            """, (system_user_id,))

            await db.commit()
            logger.info(f"Created system user and assigned {count} existing documents")
        else:
            await db.commit()
            logger.info("No existing documents to migrate")


async def init_sqlite():
    """Initialize SQLite database with schema"""
    db_path = Path(settings.sqlite_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(settings.sqlite_path) as db:
        # Users table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                username TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        """)

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
                tags TEXT,  -- JSON array as string
                user_id TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
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

        # Ensure all columns exist in entities table (migration support)
        cursor = await db.execute("PRAGMA table_info(entities)")
        existing_columns = {row[1] for row in await cursor.fetchall()}

        if 'mention_count' not in existing_columns:
            await db.execute("ALTER TABLE entities ADD COLUMN mention_count INTEGER DEFAULT 1")
            logger.info("Added mention_count column to entities table")

        if 'variants' not in existing_columns:
            await db.execute("ALTER TABLE entities ADD COLUMN variants TEXT")
            logger.info("Added variants column to entities table")

        if 'description' not in existing_columns:
            await db.execute("ALTER TABLE entities ADD COLUMN description TEXT")
            logger.info("Added description column to entities table")

        if 'created_at' not in existing_columns:
            await db.execute("ALTER TABLE entities ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            logger.info("Added created_at column to entities table")

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

        # Relationships table (links entities to entities)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS relationships (
                id TEXT PRIMARY KEY,
                source_entity_id TEXT NOT NULL,
                target_entity_id TEXT NOT NULL,
                relationship_type TEXT NOT NULL,
                context TEXT,
                chunk_id TEXT,
                confidence REAL DEFAULT 1.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_entity_id) REFERENCES entities(id) ON DELETE CASCADE,
                FOREIGN KEY (target_entity_id) REFERENCES entities(id) ON DELETE CASCADE,
                FOREIGN KEY (chunk_id) REFERENCES chunks(id) ON DELETE CASCADE
            )
        """)

        # Check if user_id column exists in documents (for migration support)
        cursor = await db.execute("PRAGMA table_info(documents)")
        doc_columns = {row[1] for row in await cursor.fetchall()}

        # Create indices for performance
        await db.execute("CREATE INDEX IF NOT EXISTS idx_entity_mentions_entity ON entity_mentions(entity_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_entity_mentions_chunk ON entity_mentions(chunk_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_relationships_source ON relationships(source_entity_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_relationships_target ON relationships(target_entity_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_relationships_type ON relationships(relationship_type)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_documents_collection ON documents(collection)")

        # Only create user_id index if column exists
        if 'user_id' in doc_columns:
            await db.execute("CREATE INDEX IF NOT EXISTS idx_documents_user ON documents(user_id)")

        await db.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")

        await db.commit()
        logger.info("SQLite initialized")


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
        logger.info(f"Qdrant collection '{collection_name}' created")
    else:
        logger.info(f"Qdrant collection '{collection_name}' already exists")


async def init_kuzu():
    """Initialize Kuzu graph database (Phase 2)"""
    import kuzu

    db_path = Path(settings.kuzu_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    db = kuzu.Database(settings.kuzu_path)
    conn = kuzu.Connection(db)

    # Check if tables exist
    try:
        result = conn.execute("SHOW TABLES")
        existing_tables = {row[0] for row in result.get_as_df()['name'].tolist()}
    except Exception:
        existing_tables = set()

    # Create node tables if they don't exist
    try:
        if 'Entity' not in existing_tables:
            conn.execute("CREATE NODE TABLE Entity(name STRING, type STRING, description STRING, PRIMARY KEY(name))")
            logger.info("Created Kuzu Entity table")

        if 'Chunk' not in existing_tables:
            conn.execute("CREATE NODE TABLE Chunk(id STRING, content STRING, PRIMARY KEY(id))")
            logger.info("Created Kuzu Chunk table")

        # Create relationship tables if they don't exist
        if 'MENTIONED_IN' not in existing_tables:
            conn.execute("CREATE REL TABLE MENTIONED_IN(FROM Entity TO Chunk, context STRING)")
            logger.info("Created Kuzu MENTIONED_IN relationship")

        if 'RELATES_TO' not in existing_tables:
            conn.execute("CREATE REL TABLE RELATES_TO(FROM Entity TO Entity, type STRING, context STRING)")
            logger.info("Created Kuzu RELATES_TO relationship")

        logger.info("Kuzu graph initialized")
    except Exception as e:
        logger.warning(f"Kuzu initialization error: {e}")


async def init_databases():
    """Initialize all databases"""
    await init_sqlite()
    await migrate_collections()
    await migrate_add_users()
    await init_qdrant()
    await init_kuzu()
