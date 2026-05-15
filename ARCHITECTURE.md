# Architecture

This document explains the technical architecture of Recall.

## High-Level Overview

```
┌─────────────┐
│   Client    │
│  (Browser)  │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────┐
│         FastAPI Backend                 │
│                                         │
│  ┌──────────┐  ┌──────────┐           │
│  │  Ingest  │  │  Search  │           │
│  │   API    │  │   API    │           │
│  └────┬─────┘  └────┬─────┘           │
│       │             │                  │
│  ┌────▼─────────────▼──────┐          │
│  │  Document Services       │          │
│  │  - Loader                │          │
│  │  - Chunker               │          │
│  │  - Embedder              │          │
│  └──────────────────────────┘          │
└─────────┬───────────┬────────┬─────────┘
          │           │        │
          ▼           ▼        ▼
    ┌─────────┐ ┌─────────┐ ┌─────────┐
    │ SQLite  │ │ Qdrant  │ │  Kuzu   │
    │Metadata │ │ Vectors │ │  Graph  │
    └─────────┘ └─────────┘ └─────────┘
```

## Component Details

### 1. Document Ingestion Pipeline

```python
Upload File → Extract Text → Chunk → Embed → Store
```

**Steps**:
1. User uploads document (PDF, DOCX, TXT, MD)
2. `document_loader.py` extracts raw text
3. `chunking.py` splits text into overlapping chunks (~512 chars)
4. `embedding.py` generates vector embeddings (384-dim)
5. Store in three places:
   - SQLite: document metadata
   - SQLite: chunk text (for retrieval)
   - Qdrant: chunk embeddings (for semantic search)

### 2. Semantic Search

```python
Query → Embed → Vector Search → Rank → Return
```

**Steps**:
1. User query is embedded using same model
2. Qdrant performs cosine similarity search
3. Top K most similar chunks are returned
4. Results include chunk content + metadata

### 3. RAG Chat (Phase 1)

```python
Query → Search → Context → [LLM] → Response
```

**Current (MVP)**:
- Returns relevant chunks as context
- User sees matching passages

**Phase 2** (with LLM):
- Query embedded and searched
- Top chunks used as context
- LLM generates answer grounded in context

### 4. Knowledge Graph (Phase 2)

```python
Chunk → Entity Extraction → Graph Building → Graph Query
```

**Planned**:
1. Extract entities from chunks (spaCy or LLM)
   - PERSON, ORG, CONCEPT, etc.
2. Extract relationships between entities
3. Store in Kuzu graph:
   - Nodes: entities
   - Edges: relationships
4. Hybrid retrieval:
   - Vector search finds relevant chunks
   - Graph traversal finds related entities
   - Combine for richer context

## Data Models

### Document
```python
{
    "id": "uuid",
    "title": "document.pdf",
    "source_type": "file",
    "file_type": "pdf",
    "num_chunks": 42,
    "created_at": "2024-01-01T00:00:00",
    "tags": ["ml", "research"],
    "collection": "school"
}
```

### Chunk
```python
{
    "id": "uuid",
    "document_id": "uuid",
    "content": "text content...",
    "chunk_index": 0,
    "embedding": [0.1, 0.2, ...]  # 384-dim vector
}
```

### Entity (Phase 2)
```python
{
    "id": "uuid",
    "name": "Neural Networks",
    "entity_type": "CONCEPT",
    "chunk_ids": ["uuid1", "uuid2"]
}
```

### Relationship (Phase 2)
```python
{
    "source": "Neural Networks",
    "target": "Deep Learning",
    "type": "PART_OF",
    "context": "snippet from source"
}
```

## Storage Layer

### SQLite
- **Purpose**: Metadata and quick lookups
- **Tables**:
  - `documents`: source files and metadata
  - `chunks`: chunk text and positions
  - `entities`: extracted entities (Phase 2)

### Qdrant
- **Purpose**: Vector similarity search
- **Collection**: `recall_chunks`
- **Vector size**: 384 (all-MiniLM-L6-v2)
- **Payload**: chunk content + metadata for display

### Kuzu (Phase 2)
- **Purpose**: Knowledge graph
- **Schema**:
  - Entity nodes
  - Chunk nodes
  - MENTIONED_IN edges (entity → chunk)
  - RELATES_TO edges (entity → entity)

## Embedding Strategy

**Model**: `sentence-transformers/all-MiniLM-L6-v2`
- **Size**: 384 dimensions
- **Speed**: Fast on CPU
- **Quality**: Good for general text
- **Alternative**: Can swap to OpenAI embeddings for better quality

**Why local embeddings?**
- No API costs
- Privacy (data never leaves your machine)
- Fast batch processing
- Easy to run in Docker

## Chunking Strategy

**Current**: Character-based with sentence boundary detection
- Default: 512 chars, 50 char overlap
- Tries to break at sentence boundaries

**Future enhancements**:
- Semantic chunking (group by topic)
- Markdown-aware chunking
- Sliding window with dynamic overlap

## API Design

**RESTful design**:
- `POST /api/ingest/upload` - upload document
- `GET /api/ingest/documents` - list documents
- `DELETE /api/ingest/documents/{id}` - delete document
- `GET /api/search` - semantic search
- `POST /api/chat` - RAG chat

**OpenAPI docs**: Auto-generated at `/docs`

## Scalability Considerations

**Current (single machine)**:
- SQLite: good for 100K+ documents
- Qdrant: can handle millions of vectors
- Kuzu: embedded, scales to machine memory

**Future (distributed)**:
- Replace SQLite with PostgreSQL
- Qdrant can cluster
- Replace Kuzu with Neo4j for multi-node graph

## Security

**Current**:
- No authentication (local use only)
- File upload validation
- No code execution

**Phase 3**:
- JWT authentication
- User-specific collections
- Rate limiting
- Input sanitization

## Performance

**Ingestion**:
- ~1-2 seconds per PDF page
- Batched embedding generation
- Async I/O for parallel processing

**Search**:
- <100ms for vector search
- Scales with collection size
- Can add approximate nearest neighbor for speed

**Graph (Phase 2)**:
- Graph queries: <100ms for 2-3 hop traversal
- Depends on graph size and complexity
