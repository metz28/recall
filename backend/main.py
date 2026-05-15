"""
Recall - Personal Knowledge Base with RAG
Main FastAPI application entry point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from core.config import settings
from api import ingest, search, chat
from db.init_db import init_databases


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize databases on startup"""
    print("🚀 Starting Recall...")
    await init_databases()
    print("✅ Databases initialized")

    # Preload embedding model (takes 30-60 seconds on first run)
    print("📦 Loading embedding model (this may take a minute)...")
    from services.embedding import get_embedding_model
    get_embedding_model()
    print("✅ Embedding model loaded")

    yield
    print("👋 Shutting down Recall...")


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
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])


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
