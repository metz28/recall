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

    # Notion Configuration (optional)
    notion_api_key: str | None = None

    # Chunking Configuration
    chunk_size: int = 512
    chunk_overlap: int = 50

    # Entity Extraction Configuration
    entity_extraction_enabled: bool = True
    entity_extraction_method: str = "spacy"  # "spacy" or "llm"
    spacy_model: str = "en_core_web_sm"
    entity_types: str = "PERSON,ORG,GPE,PRODUCT,EVENT,WORK_OF_ART,LAW,NORP,FAC"
    entity_context_window: int = 100
    llm_model: str = "claude-3-haiku-20240307"  # Fast and cost-effective for extraction

    # Relationship Extraction Configuration
    relationship_extraction_enabled: bool = True
    relationship_extraction_method: str = "llm"  # Currently only "llm" supported

    # Hybrid Search Configuration
    hybrid_search_enabled: bool = True
    hybrid_search_default_alpha: float = 0.7
    hybrid_search_default_graph_depth: int = 1
    hybrid_search_max_graph_depth: int = 3
    hybrid_search_default_expansion_limit: int = 5
    hybrid_search_max_expansion_limit: int = 20
    hybrid_search_min_vector_score: float = 0.3

    # Logging Configuration
    log_level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL

    # Application Settings
    max_upload_size: int = 50  # MB
    allowed_extensions: str = ".txt,.pdf,.docx,.md,.html"

    class Config:
        env_file = ".env"
        case_sensitive = False

    @property
    def allowed_extensions_list(self) -> list[str]:
        return [ext.strip() for ext in self.allowed_extensions.split(",")]

    @property
    def entity_types_set(self) -> set[str]:
        return {et.strip() for et in self.entity_types.split(",")}


settings = Settings()
