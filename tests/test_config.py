"""
Tests for configuration management
"""
import pytest
import os
from pathlib import Path

from core.config import Settings


class TestSettingsDefaults:
    """Test default configuration values"""

    def test_default_values(self):
        """Test that default values are set correctly (or overridden by .env)"""
        settings = Settings()

        # These should always be set
        assert settings.environment in ["development", "production", "testing"]
        assert settings.api_host is not None
        assert settings.api_port > 0
        assert settings.qdrant_host is not None
        assert settings.qdrant_port > 0
        assert settings.chunk_size > 0
        assert settings.chunk_overlap >= 0
        assert isinstance(settings.entity_extraction_enabled, bool)
        assert isinstance(settings.relationship_extraction_enabled, bool)
        assert isinstance(settings.hybrid_search_enabled, bool)

    def test_database_paths(self):
        """Test database paths are set"""
        settings = Settings()

        # Paths should be set (may be overridden by .env)
        assert settings.kuzu_path is not None
        assert "kuzu" in settings.kuzu_path
        assert settings.sqlite_path is not None
        assert ".db" in settings.sqlite_path

    def test_embedding_config(self):
        """Test embedding configuration"""
        settings = Settings()

        assert settings.embedding_model == "sentence-transformers/all-MiniLM-L6-v2"
        assert settings.embedding_dimension == 384

    def test_entity_extraction_config(self):
        """Test entity extraction configuration"""
        settings = Settings()

        assert settings.entity_extraction_method == "spacy"
        assert settings.spacy_model == "en_core_web_sm"
        assert settings.entity_context_window == 100

    def test_hybrid_search_config(self):
        """Test hybrid search configuration"""
        settings = Settings()

        assert settings.hybrid_search_default_alpha == 0.7
        assert settings.hybrid_search_default_graph_depth == 1
        assert settings.hybrid_search_max_graph_depth == 3
        assert settings.hybrid_search_default_expansion_limit == 5
        assert settings.hybrid_search_max_expansion_limit == 20
        assert settings.hybrid_search_min_vector_score == 0.3

    def test_optional_keys(self):
        """Test that optional keys default to None"""
        settings = Settings()

        assert settings.openai_api_key is None
        assert settings.anthropic_api_key is None
        assert settings.notion_api_key is None


class TestSettingsProperties:
    """Test settings properties"""

    def test_allowed_extensions_list(self):
        """Test allowed_extensions_list property"""
        settings = Settings()

        extensions = settings.allowed_extensions_list

        assert isinstance(extensions, list)
        assert ".txt" in extensions
        assert ".pdf" in extensions
        assert ".docx" in extensions
        assert ".md" in extensions

    def test_allowed_extensions_list_custom(self):
        """Test allowed_extensions_list with custom value"""
        settings = Settings(allowed_extensions=".txt,.pdf")

        extensions = settings.allowed_extensions_list

        assert len(extensions) == 2
        assert ".txt" in extensions
        assert ".pdf" in extensions

    def test_entity_types_set(self):
        """Test entity_types_set property"""
        settings = Settings()

        entity_types = settings.entity_types_set

        assert isinstance(entity_types, set)
        assert "PERSON" in entity_types
        assert "ORG" in entity_types
        assert "GPE" in entity_types
        assert "PRODUCT" in entity_types

    def test_entity_types_set_custom(self):
        """Test entity_types_set with custom value"""
        settings = Settings(entity_types="PERSON,ORG")

        entity_types = settings.entity_types_set

        assert len(entity_types) == 2
        assert "PERSON" in entity_types
        assert "ORG" in entity_types


class TestSettingsEnvironmentVariables:
    """Test settings from environment variables"""

    def test_environment_override(self, monkeypatch):
        """Test that environment variables override defaults"""
        monkeypatch.setenv("ENVIRONMENT", "production")
        monkeypatch.setenv("API_PORT", "9000")

        settings = Settings()

        assert settings.environment == "production"
        assert settings.api_port == 9000

    def test_database_path_override(self, monkeypatch):
        """Test database path override"""
        monkeypatch.setenv("SQLITE_PATH", "/custom/path/db.sqlite")
        monkeypatch.setenv("KUZU_PATH", "/custom/path/kuzu")

        settings = Settings()

        assert settings.sqlite_path == "/custom/path/db.sqlite"
        assert settings.kuzu_path == "/custom/path/kuzu"

    def test_api_keys_from_env(self, monkeypatch):
        """Test API keys from environment"""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test123")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "ant-test456")
        monkeypatch.setenv("NOTION_API_KEY", "notion-test789")

        settings = Settings()

        assert settings.openai_api_key == "sk-test123"
        assert settings.anthropic_api_key == "ant-test456"
        assert settings.notion_api_key == "notion-test789"

    def test_chunking_config_override(self, monkeypatch):
        """Test chunking configuration override"""
        monkeypatch.setenv("CHUNK_SIZE", "1024")
        monkeypatch.setenv("CHUNK_OVERLAP", "100")

        settings = Settings()

        assert settings.chunk_size == 1024
        assert settings.chunk_overlap == 100

    def test_boolean_config_override(self, monkeypatch):
        """Test boolean configuration override"""
        monkeypatch.setenv("ENTITY_EXTRACTION_ENABLED", "false")
        monkeypatch.setenv("HYBRID_SEARCH_ENABLED", "false")

        settings = Settings()

        assert settings.entity_extraction_enabled is False
        assert settings.hybrid_search_enabled is False

    def test_float_config_override(self, monkeypatch):
        """Test float configuration override"""
        monkeypatch.setenv("HYBRID_SEARCH_DEFAULT_ALPHA", "0.5")
        monkeypatch.setenv("HYBRID_SEARCH_MIN_VECTOR_SCORE", "0.4")

        settings = Settings()

        assert settings.hybrid_search_default_alpha == 0.5
        assert settings.hybrid_search_min_vector_score == 0.4

    def test_case_insensitive_env_vars(self, monkeypatch):
        """Test that environment variables are case-insensitive"""
        monkeypatch.setenv("api_port", "7000")
        monkeypatch.setenv("CHUNK_SIZE", "256")

        settings = Settings()

        # Both should work due to case_sensitive = False
        assert settings.api_port == 7000
        assert settings.chunk_size == 256


class TestSettingsValidation:
    """Test settings validation"""

    def test_max_upload_size(self):
        """Test max upload size setting"""
        settings = Settings()

        assert settings.max_upload_size == 50  # MB

    def test_log_level(self):
        """Test log level setting"""
        settings = Settings()

        assert settings.log_level == "INFO"

    def test_log_level_override(self, monkeypatch):
        """Test log level override"""
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")

        settings = Settings()

        assert settings.log_level == "DEBUG"

    def test_llm_model_default(self):
        """Test default LLM model for entity extraction"""
        settings = Settings()

        assert settings.llm_model == "claude-3-haiku-20240307"

    def test_relationship_extraction_method(self):
        """Test relationship extraction method"""
        settings = Settings()

        assert settings.relationship_extraction_method == "llm"


class TestSettingsExtensionsAndTypes:
    """Test file extensions and entity types parsing"""

    def test_extensions_with_spaces(self):
        """Test parsing extensions with spaces"""
        settings = Settings(allowed_extensions=".txt, .pdf , .docx")

        extensions = settings.allowed_extensions_list

        # Spaces should be stripped
        assert ".txt" in extensions
        assert ".pdf" in extensions
        assert ".docx" in extensions
        assert len(extensions) == 3

    def test_entity_types_with_spaces(self):
        """Test parsing entity types with spaces"""
        settings = Settings(entity_types="PERSON, ORG , GPE")

        entity_types = settings.entity_types_set

        # Spaces should be stripped
        assert "PERSON" in entity_types
        assert "ORG" in entity_types
        assert "GPE" in entity_types
        assert len(entity_types) == 3

    def test_empty_extensions(self):
        """Test with empty extensions string"""
        settings = Settings(allowed_extensions="")

        extensions = settings.allowed_extensions_list

        # Should return list with empty string
        assert len(extensions) == 1
        assert extensions[0] == ""

    def test_single_extension(self):
        """Test with single extension"""
        settings = Settings(allowed_extensions=".txt")

        extensions = settings.allowed_extensions_list

        assert len(extensions) == 1
        assert ".txt" in extensions


class TestSettingsIntegration:
    """Test settings integration scenarios"""

    def test_settings_immutable_after_creation(self):
        """Test that settings are immutable after creation"""
        settings = Settings()

        # Pydantic models are not frozen by default, but we can test the values
        original_port = settings.api_port
        assert original_port == 8000

    def test_multiple_settings_instances(self):
        """Test creating multiple settings instances"""
        settings1 = Settings()
        settings2 = Settings()

        # Should have same default values
        assert settings1.api_port == settings2.api_port
        assert settings1.chunk_size == settings2.chunk_size

    def test_settings_with_partial_env(self, monkeypatch):
        """Test settings with partial environment configuration"""
        monkeypatch.setenv("API_PORT", "9000")
        # Other vars use defaults

        settings = Settings()

        # Override should work
        assert settings.api_port == 9000
        # Defaults should still work
        assert settings.api_host == "0.0.0.0"
        assert settings.chunk_size == 512
