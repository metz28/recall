"""
Recall - Personal Knowledge Base with RAG
Main FastAPI application entry point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from core.config import settings
from core.logging_config import setup_logging, get_logger
from api import ingest, search, chat, entities, hybrid_search, graph, notion, collections
from db.init_db import init_databases

# Initialize logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize databases on startup"""
    logger.info("Starting Recall...")
    await init_databases()
    logger.info("Databases initialized")

    # Preload embedding model (takes 30-60 seconds on first run)
    logger.info("Loading embedding model (this may take a minute)...")
    from services.embedding import get_embedding_model
    get_embedding_model()
    logger.info("Embedding model loaded")

    # Preload spaCy model for entity extraction
    if settings.entity_extraction_enabled:
        logger.info("Loading spaCy model for entity extraction...")
        from services.entity_extraction import get_spacy_model
        try:
            get_spacy_model(settings.spacy_model)
            logger.info("spaCy model loaded")
        except Exception as e:
            logger.warning(f"Could not load spaCy model: {e}")
            logger.warning("Entity extraction will be disabled")

    yield
    logger.info("Shutting down Recall...")


app = FastAPI(
    title="Recall API",
    description="Personal knowledge base with hybrid vector + graph retrieval",
    version="0.1.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(ingest.router, prefix="/api/ingest", tags=["ingest"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(hybrid_search.router, prefix="/api/search/hybrid", tags=["search"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(entities.router, prefix="/api/entities", tags=["entities"])
app.include_router(graph.router, prefix="/api/graph", tags=["graph"])
app.include_router(notion.router, prefix="/api/notion", tags=["notion"])
app.include_router(collections.router, prefix="/api/collections", tags=["collections"])


@app.get("/")
async def root():
    return {
        "message": "Recall API",
        "version": "0.1.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}
