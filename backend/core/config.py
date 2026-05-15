"""
Configuration management using pydantic-settings
"""
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # API Configuration
    environment: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Database Configuration
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    kuzu_path: str = "./data/kuzu"
    sqlite_path: str = "./data/recall.db"

    # Embedding Configuration
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    # LLM Configuration (optional)
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    # Chunking Configuration
    chunk_size: int = 512
    chunk_overlap: int = 50

    # Application Settings
    max_upload_size: int = 50  # MB
    allowed_extensions: str = ".txt,.pdf,.docx,.md,.html"

    class Config:
        env_file = ".env"
        case_sensitive = False

    @property
    def allowed_extensions_list(self) -> list[str]:
        return [ext.strip() for ext in self.allowed_extensions.split(",")]


settings = Settings()
