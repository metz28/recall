# Recall

A personal knowledge base with hybrid vector + graph retrieval. Drop in PDFs, docs, or plain text → ask questions in chat, get answers grounded in your own knowledge.

## What Makes This Different

- **Hybrid Retrieval**: Combines vector search (semantic similarity) with knowledge graph (entity relationships)
- **Entity Extraction**: Automatically builds a knowledge graph of people, organizations, concepts, and their relationships
- **Self-Contained**: Runs entirely in Docker with no external dependencies
- **Production-Ready Architecture**: FastAPI backend, Qdrant for vectors, Kuzu for graphs, SQLite for metadata

## Tech Stack

- **Backend**: FastAPI + Python 3.11
- **Vector Store**: Qdrant
- **Graph Database**: Kuzu (embedded, no server needed)
- **Metadata Store**: SQLite
- **Embeddings**: sentence-transformers (local)
- **Document Processing**: PyMuPDF, python-docx

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

## Development

### Project Structure

```
recall/
├── backend/
│   ├── main.py              # FastAPI app entry point
│   ├── core/
│   │   └── config.py        # Configuration management
│   ├── api/
│   │   ├── ingest.py        # Document upload & processing
│   │   ├── search.py        # Semantic search
│   │   └── chat.py          # RAG chat endpoints
│   ├── services/
│   │   ├── document_loader.py  # PDF, DOCX, TXT parsing
│   │   ├── chunking.py         # Text chunking
│   │   └── embedding.py        # Sentence transformers
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
curl -X POST "http://localhost:8000/api/ingest/upload" \
  -F "file=@document.pdf"
```

### Search

```bash
curl "http://localhost:8000/api/search?query=machine+learning&limit=5"
```

### Chat (RAG)

```bash
curl -X POST "http://localhost:8000/api/chat" \
  -H "Content-Type: application/json" \
  -d '{"message": "What does the document say about neural networks?", "num_context_chunks": 5}'
```

### List Documents

```bash
curl "http://localhost:8000/api/ingest/documents"
```

## Roadmap

### Phase 1: MVP (Current)
- [x] Document ingestion (PDF, DOCX, TXT, MD)
- [x] Text chunking and embedding
- [x] Vector storage in Qdrant
- [x] Semantic search API
- [x] Basic RAG chat endpoint
- [ ] Simple web UI

### Phase 2: Knowledge Graph
- [ ] Entity extraction (spaCy or LLM)
- [ ] Relationship extraction
- [ ] Kuzu graph integration
- [ ] Hybrid retrieval (vector + graph)
- [ ] Graph visualization

### Phase 3: Advanced Features
- [ ] Collections/Workspaces (separate knowledge bases)
- [ ] Tags and filters
- [ ] Full LLM integration (OpenAI/Anthropic)
- [ ] Authentication
- [ ] Shareable links
- [ ] Export/import

## Configuration

Key environment variables in `.env`:

```bash
# Embedding model
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIMENSION=384

# Chunking
CHUNK_SIZE=512
CHUNK_OVERLAP=50

# Optional: LLM integration
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

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