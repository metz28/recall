"""
Embedding service using sentence-transformers
"""

from sentence_transformers import SentenceTransformer
from functools import lru_cache

from core.config import settings
from core.logging_config import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    """Load and cache the embedding model"""
    logger.info(f"Loading embedding model: {settings.embedding_model}")
    return SentenceTransformer(settings.embedding_model)


def embed_text(text: str) -> list[float]:
    """Generate embedding for a single text"""
    model = get_embedding_model()
    embedding = model.encode(text, convert_to_numpy=True)
    return embedding.tolist()


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for multiple texts"""
    model = get_embedding_model()
    embeddings = model.encode(texts, convert_to_numpy=True, show_progress_bar=True)
    return embeddings.tolist()
