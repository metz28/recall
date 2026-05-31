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

### Phase 4: Collaboration & Export (Planned)
- [ ] Authentication and user management
- [ ] Shareable links for documents and searches
- [ ] Export/import functionality
- [ ] Multi-user collaboration
- [ ] API key management
- [ ] Advanced permissions

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