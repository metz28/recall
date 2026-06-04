# Recall

A personal knowledge base with hybrid vector + graph retrieval. Drop in PDFs, docs, or plain text → ask questions in chat, get answers grounded in your own knowledge.

## What Makes This Different

- **Hybrid Retrieval**: Combines vector search (semantic similarity) with knowledge graph (entity relationships)
- **Entity Extraction**: Automatically builds a knowledge graph of people, organizations, concepts, and their relationships
- **Tags & Collections**: Organize documents with tags and collections for powerful filtering
- **Graph Visualization**: Interactive knowledge graph visualization with entity relationships
- **Modern Web UI**: React TypeScript interface with drag-and-drop upload, search, and graph exploration
- **Self-Contained**: Runs entirely in Docker with no external dependencies
- **Production-Ready Architecture**: FastAPI backend, Qdrant for vectors, Kuzu for graphs, SQLite for metadata

## Tech Stack

- **Frontend**: React 18 + TypeScript + Vite + Tailwind CSS
- **Backend**: FastAPI + Python 3.11
- **Vector Store**: Qdrant
- **Graph Database**: Kuzu (embedded, no server needed)
- **Metadata Store**: SQLite
- **Embeddings**: sentence-transformers (local)
- **Document Processing**: PyMuPDF, python-docx

## Authentication

Recall now supports multi-user authentication with JWT tokens. Each user has their own private documents and collections.

### First-Time Setup

1. **Generate a secure JWT secret key:**
   ```bash
   openssl rand -hex 32
   ```

2. **Configure environment variables:**
   Create a `.env` file from the example:
   ```bash
   cp .env.example .env
   ```

   Edit `.env` and set:
   ```env
   JWT_SECRET_KEY=<your-generated-secret-key>
   FRONTEND_URL=http://localhost:5173
   ```

3. **Install dependencies** (if not using Docker):
   ```bash
   pip install -r requirements.txt
   ```

### Creating Your First User

After starting the application, navigate to `http://localhost:5173/register` to create your account.

- **Email**: Must be a valid email address
- **Username**: Minimum 3 characters, alphanumeric
- **Password**: Minimum 8 characters

### Migrating Existing Data

If you have existing documents before authentication was added:
1. All existing documents are automatically assigned to a system user during migration
2. The first real user you create can claim or re-upload these documents
3. Or use admin tools to transfer document ownership (requires manual database access)

## API Key Management

Recall supports API key authentication for programmatic access, allowing you to integrate Recall with scripts, automation tools, and other applications.

### Creating API Keys

API keys provide full access to your account and can be used in place of JWT tokens:

```bash
# First, authenticate and get a JWT token
TOKEN=$(curl -X POST "http://localhost:8000/api/auth/login" \
  -d "email=user@example.com&password=yourpassword" | jq -r '.access_token')

# Create an API key
curl -X POST "http://localhost:8000/api/v1/api-keys" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Script Key",
    "expires_at": null
  }'
```

**Important:** The full API key is shown only once when created. Save it securely!

### Using API Keys

Use your API key in the Authorization header just like a JWT token:

```bash
# Use API key for authentication
API_KEY="recall_sk_prod_a1b2c3d4..."

curl "http://localhost:8000/api/search?query=machine+learning" \
  -H "Authorization: Bearer $API_KEY"
```

API keys work with all endpoints that accept JWT authentication.

### Managing API Keys

```bash
# List your API keys (only shows prefixes for security)
curl "http://localhost:8000/api/v1/api-keys" \
  -H "Authorization: Bearer $TOKEN"

# Disable an API key without deleting it
curl -X PUT "http://localhost:8000/api/v1/api-keys/{key_id}/toggle" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"is_active": false}'

# Delete an API key
curl -X DELETE "http://localhost:8000/api/v1/api-keys/{key_id}" \
  -H "Authorization: Bearer $TOKEN"
```

### API Key Features

- **Full Access:** API keys grant the same permissions as the owning user
- **Optional Expiration:** Set expiration dates for temporary keys
- **Enable/Disable:** Soft-disable keys without deletion
- **Activity Tracking:** last_used_at timestamp updates on each use
- **Secure Storage:** Keys are hashed with bcrypt (SHA256 + bcrypt for long keys)

## Role-Based Access Control (RBAC)

Recall includes a flexible RBAC system for fine-grained permission management, perfect for team collaboration and document sharing.

### System Roles

Five predefined roles are available out of the box:

1. **Viewer**: Read-only access to documents, collections, and search
   - Permissions: `document:read`, `collection:read`, `search:execute`

2. **Editor**: Can view and edit documents and collections
   - Permissions: All viewer permissions + `document:write`, `collection:write`, `export:create`

3. **Analyst**: Advanced search and analytics
   - Permissions: Viewer permissions + `search:advanced`, `graph:explore`, `entity:view`, `export:create`

4. **Admin**: Full management except document deletion
   - Permissions: Editor permissions + `document:share`, `collection:manage`, `collaborator:add`, `collaborator:remove`, `role:assign`

5. **Owner**: Complete control (automatic for document creators)
   - Permissions: `*:*` (wildcard for all permissions)

### Permission Format

Permissions use the format `{resource}:{action}`:
- `document:read`, `document:write`, `document:delete`, `document:share`
- `collection:read`, `collection:write`, `collection:manage`
- `search:execute`, `search:advanced`
- `collaborator:add`, `collaborator:remove`
- `role:assign`
- `*:*` (wildcard for owners)

### Creating Custom Roles

Create roles with specific permission combinations:

```bash
# Create a custom role
curl -X POST "http://localhost:8000/api/v1/roles" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "research_analyst",
    "display_name": "Research Analyst",
    "description": "Can search and export but not edit",
    "permissions": [
      "document:read",
      "search:execute",
      "search:advanced",
      "graph:explore",
      "export:create"
    ]
  }'
```

### Assigning Roles

Assign roles to users for specific documents or collections:

```bash
# Assign viewer role to a user for a specific document
curl -X POST "http://localhost:8000/api/v1/role-assignments" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "role_id": "{role_id}",
    "user_id": "{collaborator_user_id}",
    "resource_type": "document",
    "resource_id": "{document_id}"
  }'

# Assign global role (applies to all resources)
curl -X POST "http://localhost:8000/api/v1/role-assignments" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "role_id": "{role_id}",
    "user_id": "{user_id}",
    "resource_type": "global",
    "resource_id": null
  }'
```

### Permission Checking

Check if a user has specific permissions:

```bash
# Check permission
curl -X POST "http://localhost:8000/api/v1/permissions/check" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "{user_id}",
    "resource_type": "document",
    "resource_id": "{document_id}",
    "permission": "document:write"
  }'

# Get all permissions for current user on a resource
curl "http://localhost:8000/api/v1/permissions/me/document/{document_id}" \
  -H "Authorization: Bearer $TOKEN"
```

### Managing Roles

```bash
# List all roles (system and custom)
curl "http://localhost:8000/api/v1/roles" \
  -H "Authorization: Bearer $TOKEN"

# Get role details
curl "http://localhost:8000/api/v1/roles/{role_id}" \
  -H "Authorization: Bearer $TOKEN"

# Update custom role
curl -X PUT "http://localhost:8000/api/v1/roles/{role_id}" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "description": "Updated description",
    "permissions": ["document:read", "search:execute"]
  }'

# Delete custom role
curl -X DELETE "http://localhost:8000/api/v1/roles/{role_id}" \
  -H "Authorization: Bearer $TOKEN"
```

### Backward Compatibility

The existing collaboration system works seamlessly with RBAC:
- Adding collaborators with `read`, `write`, or `admin` permissions automatically creates corresponding role assignments
- Old permission: `read` → Role: `viewer`
- Old permission: `write` → Role: `editor`
- Old permission: `admin` → Role: `admin`

## Quick Start

### Option 1: Simple Local Setup (Recommended)

The easiest way to run Recall locally:

```bash
# First time setup
python local/recall.py setup

# Start Recall
python local/recall.py run
```

See **[local/README.md](local/README.md)** for full instructions.

**Requirements:** Python 3.11+

### Option 2: Docker

If you prefer containers:

```bash
# Start everything
docker-compose up --build

# Stop everything
docker-compose down
```

**Requirements:** Docker & Docker Compose

### Access Points

Once running:
- **API Docs:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/health
- **Qdrant Dashboard:** http://localhost:6333/dashboard

### Web UI (Optional)

For a modern web interface, start the React frontend:

```bash
cd frontend
npm install
npm run dev
```

Then access the web UI at **http://localhost:3000**

The web UI provides:
- Drag-and-drop document upload with tag support
- Semantic search with similarity scores
- Tag-based filtering and organization
- Collection management for document workspaces
- Interactive knowledge graph visualization
- Document management and viewing

See **[frontend/README.md](frontend/README.md)** for full frontend documentation.

## Development

### Project Structure

```
recall/
├── frontend/                # React TypeScript web UI
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── api/             # Backend API client
│   │   └── types/           # TypeScript types
│   ├── package.json
│   └── vite.config.ts
├── backend/
│   ├── main.py              # FastAPI app entry point
│   ├── core/
│   │   └── config.py        # Configuration management
│   ├── api/
│   │   ├── ingest.py        # Document upload & processing
│   │   ├── search.py        # Semantic search
│   │   ├── chat.py          # RAG chat endpoints
│   │   ├── tags.py          # Tag management
│   │   ├── collections.py   # Collections/workspaces
│   │   ├── entities.py      # Entity browsing
│   │   └── graph.py         # Knowledge graph API
│   ├── services/
│   │   ├── document_loader.py  # PDF, DOCX, TXT parsing
│   │   ├── chunking.py         # Text chunking
│   │   ├── embedding.py        # Sentence transformers
│   │   ├── graph_service.py    # Kuzu graph operations
│   │   └── entity_extraction.py # Entity and relationship extraction
│   ├── models/
│   │   └── document.py      # Pydantic models
│   └── db/
│       └── init_db.py       # Database initialization
├── data/                    # Persistent data (gitignored)
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## API Usage

### Upload a Document

```bash
# Basic upload
curl -X POST "http://localhost:8000/api/ingest/upload" \
  -F "file=@document.pdf"

# Upload with tags and collection
curl -X POST "http://localhost:8000/api/ingest/upload" \
  -F "file=@document.pdf" \
  -F "tags=machine-learning,ai,research" \
  -F "collection=research-papers"
```

### Search

#### Vector Search (Semantic Similarity)

```bash
# Basic search
curl "http://localhost:8000/api/search?query=machine+learning&limit=5"

# Search with tag filter
curl "http://localhost:8000/api/search?query=neural+networks&tags=ai,deep-learning"

# Search within a collection
curl "http://localhost:8000/api/search?query=transformers&collection=research-papers"

# Combined filters
curl "http://localhost:8000/api/search?query=attention&collection=research-papers&tags=nlp,transformers"
```

#### Hybrid Search (Vector + Graph)

Combines semantic similarity with knowledge graph context for enhanced retrieval:

```bash
# Basic hybrid search (default: 70% vector, 30% graph)
curl "http://localhost:8000/api/search/hybrid?query=machine+learning&limit=10"

# Adjust weighting (50% vector, 50% graph)
curl "http://localhost:8000/api/search/hybrid?query=neural+networks&alpha=0.5"

# Graph-focused search (30% vector, 70% graph)
curl "http://localhost:8000/api/search/hybrid?query=Einstein&alpha=0.3"

# Deeper graph traversal (2 hops)
curl "http://localhost:8000/api/search/hybrid?query=quantum+computing&graph_depth=2"

# Disable graph expansion (entity overlap only)
curl "http://localhost:8000/api/search/hybrid?query=machine+learning&graph_depth=0"
```

**Hybrid Search Parameters:**
- `alpha` (0.0-1.0): Weight for vector vs graph scores (default: 0.7)
  - 1.0 = pure vector search
  - 0.5 = equal weight
  - 0.0 = pure graph search
- `graph_depth` (0-3): Number of relationship hops to traverse (default: 1)
- `graph_expansion_limit` (0-20): Max additional chunks from graph (default: 5)
- `min_vector_score` (0.0-1.0): Threshold for vector results (default: 0.3)
- `enable_entity_expansion` (bool): Enable graph traversal (default: true)

**When to use hybrid search:**
- Finding documents related to specific entities (people, organizations, concepts)
- Discovering connections between topics
- Exploring document clusters around related entities
- When pure semantic search misses important context

**When to use vector search:**
- Pure semantic similarity queries
- Speed is critical
- No entities in your knowledge base yet

### Chat (RAG)

```bash
curl -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "What does the document say about neural networks?", "num_context_chunks": 5}'
```

### Collections

```bash
# List all collections
curl "http://localhost:8000/api/collections"

# Create a collection
curl -X POST "http://localhost:8000/api/collections" \
  -H "Content-Type: application/json" \
  -d '{"name": "research-papers"}'

# Get collection stats
curl "http://localhost:8000/api/collections/research-papers/stats"

# Delete a collection
curl -X DELETE "http://localhost:8000/api/collections/research-papers"
```

### Tags

```bash
# List all tags with document counts
curl "http://localhost:8000/api/tags"

# Get tags for a specific document
curl "http://localhost:8000/api/tags/documents/{document_id}/tags"

# Update document tags
curl -X PUT "http://localhost:8000/api/tags/documents/{document_id}/tags" \
  -H "Content-Type: application/json" \
  -d '{"tags": ["machine-learning", "deep-learning", "nlp"]}'
```

### Entities & Knowledge Graph

```bash
# Search entities
curl "http://localhost:8000/api/entities?query=Einstein&limit=10"

# Get entity details with relationships
curl "http://localhost:8000/api/entities/{entity_id}"

# Get full knowledge graph
curl "http://localhost:8000/api/graph/full"

# Get graph filtered by collection
curl "http://localhost:8000/api/graph/full?collection=research-papers"

# Get entity neighborhood
curl "http://localhost:8000/api/graph/entity/{entity_id}"
```

### List Documents

```bash
curl "http://localhost:8000/api/ingest/documents"
```

### Export/Import

Export and import your knowledge base for backups or migration.

#### Export Data

```bash
# Export a single document
curl -X POST "http://localhost:8000/api/export-import/export" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "export_type": "document",
    "resource_id": "doc-uuid",
    "include_embeddings": false,
    "include_graph": true
  }' > document-export.json

# Export a collection
curl -X POST "http://localhost:8000/api/export-import/export" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "export_type": "collection",
    "resource_id": "research-papers",
    "include_embeddings": false,
    "include_graph": true
  }' > collection-export.json

# Export entire knowledge base
curl -X POST "http://localhost:8000/api/export-import/export" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "export_type": "all",
    "include_embeddings": false,
    "include_graph": true
  }' > full-export.json

# Quick export (GET request)
curl "http://localhost:8000/api/export-import/export/document/{document_id}" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  > document.json
```

#### Import Data

```bash
# Import with skip mode (default - skip existing documents)
curl -X POST "http://localhost:8000/api/export-import/import" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d @export.json

# Import with replace mode (replace existing documents)
curl -X POST "http://localhost:8000/api/export-import/import" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "data": {...},
    "import_mode": "replace",
    "regenerate_embeddings": true
  }'

# Import to a different collection
curl -X POST "http://localhost:8000/api/export-import/import" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "data": {...},
    "import_mode": "skip",
    "regenerate_embeddings": true,
    "target_collection": "imported-data"
  }'
```

**Import Modes:**
- `skip`: Skip documents that already exist (default)
- `replace`: Replace existing documents with imported versions
- `merge`: Add imported data alongside existing documents

**Options:**
- `regenerate_embeddings`: Re-generate vector embeddings on import (default: true)
- `target_collection`: Override the collection name for imported documents
- `include_embeddings`: Include vector embeddings in export (makes files large)
- `include_graph`: Include entities and relationships in export

### Collaboration

Share documents and collections with other users with granular permissions.

#### Add a Collaborator

```bash
curl -X POST "http://localhost:8000/api/collaboration/collaborators" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "resource_type": "document",
    "resource_id": "doc-uuid",
    "collaborator_email": "user@example.com",
    "permission": "write",
    "message": "Check out this document!"
  }'
```

**Permission Levels:**
- `read`: Can view the document and search within it
- `write`: Can edit metadata, tags, and add/remove from collections
- `admin`: Can share with others and remove collaborators

#### List Collaborators

```bash
curl "http://localhost:8000/api/collaboration/collaborators/document/{document_id}" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Update Collaborator Permission

```bash
curl -X PUT "http://localhost:8000/api/collaboration/collaborators/{collaborator_id}" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"permission": "admin"}'
```

#### Remove Collaborator

```bash
curl -X DELETE "http://localhost:8000/api/collaboration/collaborators/{collaborator_id}" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### View Shared With Me

```bash
# List all documents/collections shared with you
curl "http://localhost:8000/api/collaboration/shared-with-me" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Activity Log

```bash
# View activity log for a document
curl "http://localhost:8000/api/collaboration/activity/document/{document_id}" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Collaboration Stats

```bash
# Get collaboration statistics
curl "http://localhost:8000/api/collaboration/stats" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Check Permissions

```bash
# Check your permission level for a resource
curl "http://localhost:8000/api/collaboration/permissions/document/{document_id}" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Roadmap

### Phase 1: MVP ✅
- [x] Document ingestion (PDF, DOCX, TXT, MD, HTML)
- [x] Text chunking and embedding
- [x] Vector storage in Qdrant
- [x] Semantic search API
- [x] Basic RAG chat endpoint
- [x] React TypeScript web UI with upload and search

### Phase 2: Knowledge Graph ✅
- [x] Entity extraction (spaCy or LLM)
- [x] Kuzu graph integration
- [x] Relationship extraction
- [x] Hybrid retrieval (vector + graph)
- [x] Graph visualization with interactive UI

### Phase 3: Organization & Filtering ✅
- [x] Collections/Workspaces (separate knowledge bases)
- [x] Tags and tag-based filtering
- [x] Full LLM integration (Anthropic Claude)
- [x] Tag input and autocomplete UI
- [x] Multi-select tag filtering

### Phase 4: Collaboration & Export (Complete)
- [x] Authentication and user management
- [x] Shareable links for documents and searches
- [x] Export/import functionality
- [x] Multi-user collaboration with activity tracking
- [x] API key management for programmatic access
- [x] Role-Based Access Control (RBAC) with custom roles

## Configuration

Key environment variables in `.env`:

```bash
# Embedding model
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384

# Chunking
CHUNK_SIZE=512
CHUNK_OVERLAP=50

# Entity extraction
ENTITY_EXTRACTION_ENABLED=true
ENTITY_EXTRACTION_METHOD=spacy  # "spacy" or "llm"
SPACY_MODEL=en_core_web_sm
ENTITY_TYPES=PERSON,ORG,GPE,PRODUCT,EVENT,WORK_OF_ART,LAW,NORP,FAC

# LLM integration (required for LLM-based entity extraction)
ANTHROPIC_API_KEY=sk-ant-...
LLM_MODEL=claude-3-haiku-20240307

# Hybrid search (vector + graph)
HYBRID_SEARCH_ENABLED=true
HYBRID_SEARCH_DEFAULT_ALPHA=0.7
HYBRID_SEARCH_DEFAULT_GRAPH_DEPTH=1
HYBRID_SEARCH_MAX_GRAPH_DEPTH=3
HYBRID_SEARCH_DEFAULT_EXPANSION_LIMIT=5
HYBRID_SEARCH_MAX_EXPANSION_LIMIT=20
HYBRID_SEARCH_MIN_VECTOR_SCORE=0.3
```

### Entity Extraction Methods

**spaCy (default)**: Fast, free, local NER
- Pros: No API costs, works offline, very fast
- Cons: Less accurate on domain-specific entities

**LLM (Claude)**: AI-powered extraction
- Pros: Higher accuracy, better context understanding
- Cons: Requires API key, costs per document, slower

Set `ENTITY_EXTRACTION_METHOD=llm` and provide `ANTHROPIC_API_KEY` to use LLM extraction.

## Testing

```bash
# Run tests
pytest

# With coverage
pytest --cov=backend tests/
```

## Contributing

This is a personal project, but contributions are welcome! Feel free to:
- Open issues for bugs or feature requests
- Submit PRs for improvements
- Star the repo if you find it useful

## License

MIT

## Inspiration

Built for developers, researchers, and knowledge workers who want a local, extensible alternative to commercial knowledge management tools.