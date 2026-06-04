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


async def migrate_add_rbac():
    """Migrate database to add RBAC tables and seed system roles"""
    async with aiosqlite.connect(settings.sqlite_path) as db:
        # Check if roles table exists
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='roles'"
        )
        roles_table_exists = await cursor.fetchone() is not None

        if roles_table_exists:
            logger.info("RBAC tables already exist")
            # Still ensure system roles are created
            from services.rbac_service import create_system_roles
            await create_system_roles()
            return

        # Create roles table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS roles (
                id TEXT PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL,
                description TEXT,
                permissions TEXT NOT NULL,
                is_system BOOLEAN DEFAULT 0,
                is_custom BOOLEAN DEFAULT 1,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
            )
        """)

        # Create role_assignments table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS role_assignments (
                id TEXT PRIMARY KEY,
                role_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                resource_id TEXT,
                assigned_by TEXT NOT NULL,
                assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (assigned_by) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(role_id, user_id, resource_type, resource_id)
            )
        """)

        # Create indices
        await db.execute("CREATE INDEX IF NOT EXISTS idx_roles_name ON roles(name)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_roles_system ON roles(is_system)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_roles_creator ON roles(created_by)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_role_assignments_user ON role_assignments(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_role_assignments_role ON role_assignments(role_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_role_assignments_resource ON role_assignments(resource_type, resource_id)")

        await db.commit()
        logger.info("RBAC tables created successfully")

        # Create system roles
        from services.rbac_service import create_system_roles
        await create_system_roles()

        # Migrate existing collaborators to role assignments
        await _migrate_collaborators_to_roles(db)


async def _migrate_collaborators_to_roles(db: aiosqlite.Connection):
    """Migrate existing collaborators to role assignments"""
    import uuid
    from datetime import datetime

    db.row_factory = aiosqlite.Row

    # Get role IDs
    role_map = {}
    for old_perm, role_name in [("read", "viewer"), ("write", "editor"), ("admin", "admin")]:
        cursor = await db.execute("SELECT id FROM roles WHERE name = ?", (role_name,))
        role = await cursor.fetchone()
        if role:
            role_map[old_perm] = role['id']

    if not role_map:
        logger.warning("System roles not found, skipping collaborator migration")
        return

    # Get all collaborators
    cursor = await db.execute("""
        SELECT id, resource_type, resource_id, collaborator_id, permission, added_by, added_at
        FROM collaborators
    """)
    collaborators = await cursor.fetchall()

    migrated_count = 0
    for collab in collaborators:
        role_id = role_map.get(collab['permission'])
        if not role_id:
            logger.warning(f"Unknown permission: {collab['permission']}, skipping")
            continue

        # Check if role assignment already exists
        cursor = await db.execute("""
            SELECT id FROM role_assignments
            WHERE role_id = ? AND user_id = ? AND resource_type = ? AND resource_id = ?
        """, (role_id, collab['collaborator_id'], collab['resource_type'], collab['resource_id']))

        if await cursor.fetchone():
            continue  # Already migrated

        # Create role assignment
        assignment_id = str(uuid.uuid4())
        await db.execute("""
            INSERT INTO role_assignments (
                id, role_id, user_id, resource_type, resource_id,
                assigned_by, assigned_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            assignment_id, role_id, collab['collaborator_id'],
            collab['resource_type'], collab['resource_id'],
            collab['added_by'], collab['added_at']
        ))
        migrated_count += 1

    await db.commit()
    logger.info(f"Migrated {migrated_count} collaborators to role assignments")


async def migrate_add_api_keys():
    """Migrate database to add api_keys table"""
    async with aiosqlite.connect(settings.sqlite_path) as db:
        # Check if api_keys table exists
        cursor = await db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='api_keys'"
        )
        api_keys_table_exists = await cursor.fetchone() is not None

        if api_keys_table_exists:
            logger.info("API keys table already exists")
            return

        # Create api_keys table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                key_hash TEXT NOT NULL,
                key_prefix TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used_at TIMESTAMP,
                expires_at TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                scopes TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # Create indices
        await db.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_prefix ON api_keys(key_prefix)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_active ON api_keys(is_active)")

        await db.commit()
        logger.info("API keys table created successfully")


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

        # Shared links table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS shared_links (
                id TEXT PRIMARY KEY,
                token TEXT UNIQUE NOT NULL,
                resource_type TEXT NOT NULL,
                resource_id TEXT,
                owner_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                access_level TEXT DEFAULT 'view',
                is_active BOOLEAN DEFAULT 1,
                metadata TEXT,
                view_count INTEGER DEFAULT 0,
                last_accessed TIMESTAMP,
                FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # Collaborators table (multi-user collaboration)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS collaborators (
                id TEXT PRIMARY KEY,
                resource_type TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                collaborator_id TEXT NOT NULL,
                permission TEXT NOT NULL,
                added_by TEXT NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_accessed TIMESTAMP,
                FOREIGN KEY (collaborator_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (added_by) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # Activity log table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS activity_log (
                id TEXT PRIMARY KEY,
                resource_type TEXT NOT NULL,
                resource_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # API keys table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                key_hash TEXT NOT NULL,
                key_prefix TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used_at TIMESTAMP,
                expires_at TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                scopes TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
        """)

        # Roles table (RBAC)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS roles (
                id TEXT PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL,
                description TEXT,
                permissions TEXT NOT NULL,
                is_system BOOLEAN DEFAULT 0,
                is_custom BOOLEAN DEFAULT 1,
                created_by TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
            )
        """)

        # Role assignments table (RBAC)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS role_assignments (
                id TEXT PRIMARY KEY,
                role_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                resource_type TEXT NOT NULL,
                resource_id TEXT,
                assigned_by TEXT NOT NULL,
                assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (assigned_by) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(role_id, user_id, resource_type, resource_id)
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
        await db.execute("CREATE INDEX IF NOT EXISTS idx_shared_links_token ON shared_links(token)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_shared_links_owner ON shared_links(owner_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_collaborators_resource ON collaborators(resource_type, resource_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_collaborators_user ON collaborators(collaborator_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_activity_resource ON activity_log(resource_type, resource_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_activity_user ON activity_log(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_activity_created ON activity_log(created_at)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_prefix ON api_keys(key_prefix)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_active ON api_keys(is_active)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_roles_name ON roles(name)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_roles_system ON roles(is_system)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_roles_creator ON roles(created_by)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_role_assignments_user ON role_assignments(user_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_role_assignments_role ON role_assignments(role_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_role_assignments_resource ON role_assignments(resource_type, resource_id)")

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
    await migrate_add_api_keys()
    await migrate_add_rbac()
    await init_qdrant()
    await init_kuzu()
