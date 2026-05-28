"""
Tests for graph service (Kuzu database operations)
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, call
import tempfile
from pathlib import Path

from services.graph_service import (
    get_kuzu_connection,
    store_entities_in_graph,
    query_entity_graph,
    get_entity_relationships,
    store_relationships_in_graph,
    query_entity_relationships_graph,
    delete_chunk_from_graph,
    get_entities_by_chunk_id,
    get_related_entities_multi,
    get_chunks_by_entity_names
)


class TestGetKuzuConnection:
    """Test Kuzu connection management"""

    @patch("services.graph_service.kuzu")
    @patch("services.graph_service.Path")
    def test_get_connection_creates_directory(self, mock_path_class, mock_kuzu):
        """Test that connection creates parent directory"""
        # Clear LRU cache
        get_kuzu_connection.cache_clear()

        mock_path = Mock()
        mock_path.parent.mkdir = Mock()
        mock_path_class.return_value = mock_path

        mock_db = Mock()
        mock_conn = Mock()
        mock_kuzu.Database.return_value = mock_db
        mock_kuzu.Connection.return_value = mock_conn

        with patch("services.graph_service.settings") as mock_settings:
            mock_settings.kuzu_path = "/test/kuzu"

            conn = get_kuzu_connection()

            # Should create directory
            mock_path.parent.mkdir.assert_called_once_with(parents=True, exist_ok=True)
            # Should return connection
            assert conn == mock_conn

    @patch("services.graph_service.kuzu")
    def test_get_connection_cached(self, mock_kuzu):
        """Test that connection is cached"""
        get_kuzu_connection.cache_clear()

        mock_db = Mock()
        mock_conn = Mock()
        mock_kuzu.Database.return_value = mock_db
        mock_kuzu.Connection.return_value = mock_conn

        # First call
        conn1 = get_kuzu_connection()
        # Second call
        conn2 = get_kuzu_connection()

        # Should return same connection (cached)
        assert conn1 == conn2
        # Database should only be created once
        assert mock_kuzu.Database.call_count == 1


class TestStoreEntitiesInGraph:
    """Test storing entities in graph"""

    @patch("services.graph_service.get_kuzu_connection")
    def test_store_entities_basic(self, mock_get_conn):
        """Test storing entities in graph"""
        mock_conn = Mock()
        mock_get_conn.return_value = mock_conn

        entities = [
            {
                "normalized_name": "John Doe",
                "type": "PERSON",
                "context": "John Doe is a scientist"
            }
        ]

        store_entities_in_graph(entities, "chunk123", "Full chunk content here")

        # Should execute queries for chunk, entity, and relationship
        assert mock_conn.execute.call_count >= 3

    @patch("services.graph_service.get_kuzu_connection")
    def test_store_multiple_entities(self, mock_get_conn):
        """Test storing multiple entities"""
        mock_conn = Mock()
        mock_get_conn.return_value = mock_conn

        entities = [
            {"normalized_name": "Entity 1", "type": "PERSON", "context": "Context 1"},
            {"normalized_name": "Entity 2", "type": "ORG", "context": "Context 2"},
            {"normalized_name": "Entity 3", "type": "GPE", "context": "Context 3"},
        ]

        store_entities_in_graph(entities, "chunk123", "Content")

        # Should execute queries: 1 for chunk + 2*3 for entities (entity + relationship)
        assert mock_conn.execute.call_count >= 7

    @patch("services.graph_service.get_kuzu_connection")
    def test_store_entities_with_long_content(self, mock_get_conn):
        """Test that long content is truncated"""
        mock_conn = Mock()
        mock_get_conn.return_value = mock_conn

        entities = [{"normalized_name": "Entity", "type": "PERSON", "context": "x" * 300}]
        long_content = "y" * 1000

        store_entities_in_graph(entities, "chunk123", long_content)

        # Verify chunk content is limited to 500 chars
        chunk_call = mock_conn.execute.call_args_list[0]
        assert len(chunk_call[0][1]["content"]) <= 500

        # Verify context is limited to 200 chars
        context_call = mock_conn.execute.call_args_list[2]
        assert len(context_call[0][1]["context"]) <= 200

    @patch("services.graph_service.get_kuzu_connection")
    def test_store_entities_error_handling(self, mock_get_conn):
        """Test that errors are caught and logged"""
        mock_conn = Mock()
        mock_conn.execute.side_effect = Exception("Database error")
        mock_get_conn.return_value = mock_conn

        entities = [{"normalized_name": "Entity", "type": "PERSON"}]

        # Should not raise exception
        store_entities_in_graph(entities, "chunk123", "Content")

    @patch("services.graph_service.get_kuzu_connection")
    def test_store_entities_without_context(self, mock_get_conn):
        """Test storing entities without context field"""
        mock_conn = Mock()
        mock_get_conn.return_value = mock_conn

        entities = [
            {"normalized_name": "Entity", "type": "PERSON"}
            # No context field
        ]

        store_entities_in_graph(entities, "chunk123", "Content")

        # Should handle missing context gracefully
        assert mock_conn.execute.call_count >= 3


class TestQueryEntityGraph:
    """Test querying entity graph"""

    @patch("services.graph_service.get_kuzu_connection")
    def test_query_entity_with_chunks(self, mock_get_conn):
        """Test querying entity with associated chunks"""
        mock_conn = Mock()
        mock_result = Mock()

        # Mock result rows
        rows = [
            ("Entity Name", "PERSON", "Description", "chunk1", "Content 1", "Context 1"),
            ("Entity Name", "PERSON", "Description", "chunk2", "Content 2", "Context 2"),
        ]

        mock_result.has_next.side_effect = [True, True, False]
        mock_result.get_next.side_effect = rows

        mock_conn.execute.return_value = mock_result
        mock_get_conn.return_value = mock_conn

        result = query_entity_graph("Entity Name")

        assert result["name"] == "Entity Name"
        assert result["type"] == "PERSON"
        assert result["description"] == "Description"
        assert len(result["chunks"]) == 2
        assert result["chunks"][0]["chunk_id"] == "chunk1"
        assert result["chunks"][1]["chunk_id"] == "chunk2"

    @patch("services.graph_service.get_kuzu_connection")
    def test_query_entity_not_found(self, mock_get_conn):
        """Test querying non-existent entity"""
        mock_conn = Mock()
        mock_result = Mock()
        mock_result.has_next.return_value = False

        mock_conn.execute.return_value = mock_result
        mock_get_conn.return_value = mock_conn

        result = query_entity_graph("Nonexistent")

        assert result["name"] == "Nonexistent"
        assert result["type"] is None
        assert result["description"] is None
        assert len(result["chunks"]) == 0

    @patch("services.graph_service.get_kuzu_connection")
    def test_query_entity_error_handling(self, mock_get_conn):
        """Test error handling in query"""
        mock_conn = Mock()
        mock_conn.execute.side_effect = Exception("Query error")
        mock_get_conn.return_value = mock_conn

        result = query_entity_graph("Entity Name")

        # Should return error structure
        assert "error" in result
        assert result["name"] == "Entity Name"


class TestGetEntityRelationships:
    """Test getting entity relationships"""

    @patch("services.graph_service.get_kuzu_connection")
    def test_get_relationships(self, mock_get_conn):
        """Test getting related entities"""
        mock_conn = Mock()
        mock_result = Mock()

        rows = [
            ("Related Entity 1", "PERSON", 5),
            ("Related Entity 2", "ORG", 3),
        ]

        mock_result.has_next.side_effect = [True, True, False]
        mock_result.get_next.side_effect = rows

        mock_conn.execute.return_value = mock_result
        mock_get_conn.return_value = mock_conn

        result = get_entity_relationships("Entity Name")

        assert len(result) == 2
        assert result[0]["name"] == "Related Entity 1"
        assert result[0]["type"] == "PERSON"
        assert result[0]["co_occurrences"] == 5

    @patch("services.graph_service.get_kuzu_connection")
    def test_get_relationships_error(self, mock_get_conn):
        """Test error handling"""
        mock_conn = Mock()
        mock_conn.execute.side_effect = Exception("Error")
        mock_get_conn.return_value = mock_conn

        result = get_entity_relationships("Entity Name")

        assert result == []


class TestStoreRelationshipsInGraph:
    """Test storing relationships in graph"""

    @patch("services.graph_service.get_kuzu_connection")
    def test_store_relationships(self, mock_get_conn):
        """Test storing relationships"""
        mock_conn = Mock()
        mock_get_conn.return_value = mock_conn

        relationships = [
            {
                "source_entity": "Entity A",
                "target_entity": "Entity B",
                "relationship_type": "WORKS_WITH",
                "context": "They collaborate"
            }
        ]

        store_relationships_in_graph(relationships)

        # Should execute query for relationship
        mock_conn.execute.assert_called_once()

    @patch("services.graph_service.get_kuzu_connection")
    def test_store_multiple_relationships(self, mock_get_conn):
        """Test storing multiple relationships"""
        mock_conn = Mock()
        mock_get_conn.return_value = mock_conn

        relationships = [
            {"source_entity": "A", "target_entity": "B", "relationship_type": "TYPE1"},
            {"source_entity": "B", "target_entity": "C", "relationship_type": "TYPE2"},
            {"source_entity": "C", "target_entity": "A", "relationship_type": "TYPE3"},
        ]

        store_relationships_in_graph(relationships)

        assert mock_conn.execute.call_count == 3

    @patch("services.graph_service.get_kuzu_connection")
    def test_store_relationships_with_long_context(self, mock_get_conn):
        """Test that long context is truncated"""
        mock_conn = Mock()
        mock_get_conn.return_value = mock_conn

        relationships = [
            {
                "source_entity": "A",
                "target_entity": "B",
                "relationship_type": "TYPE",
                "context": "x" * 300
            }
        ]

        store_relationships_in_graph(relationships)

        # Verify context is limited to 200 chars
        call_args = mock_conn.execute.call_args[0][1]
        assert len(call_args["context"]) <= 200

    @patch("services.graph_service.get_kuzu_connection")
    def test_store_relationships_error_handling(self, mock_get_conn):
        """Test error handling"""
        mock_conn = Mock()
        mock_conn.execute.side_effect = Exception("Error")
        mock_get_conn.return_value = mock_conn

        relationships = [
            {"source_entity": "A", "target_entity": "B", "relationship_type": "TYPE"}
        ]

        # Should not raise
        store_relationships_in_graph(relationships)


class TestDeleteChunkFromGraph:
    """Test deleting chunks from graph"""

    @patch("services.graph_service.get_kuzu_connection")
    def test_delete_chunk(self, mock_get_conn):
        """Test deleting a chunk"""
        mock_conn = Mock()
        mock_get_conn.return_value = mock_conn

        delete_chunk_from_graph("chunk123")

        # Should execute delete query
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        assert "chunk123" in str(call_args)

    @patch("services.graph_service.get_kuzu_connection")
    def test_delete_chunk_error_handling(self, mock_get_conn):
        """Test error handling in delete"""
        mock_conn = Mock()
        mock_conn.execute.side_effect = Exception("Error")
        mock_get_conn.return_value = mock_conn

        # Should not raise
        delete_chunk_from_graph("chunk123")


class TestGetEntitiesByChunkId:
    """Test getting entities by chunk ID"""

    @patch("services.graph_service.get_kuzu_connection")
    def test_get_entities_by_chunk(self, mock_get_conn):
        """Test getting entities for a chunk"""
        mock_conn = Mock()
        mock_result = Mock()

        rows = [("Entity 1",), ("Entity 2",), ("Entity 3",)]
        mock_result.has_next.side_effect = [True, True, True, False]
        mock_result.get_next.side_effect = rows

        mock_conn.execute.return_value = mock_result
        mock_get_conn.return_value = mock_conn

        result = get_entities_by_chunk_id("chunk123")

        assert len(result) == 3
        assert result == ["Entity 1", "Entity 2", "Entity 3"]

    @patch("services.graph_service.get_kuzu_connection")
    def test_get_entities_no_results(self, mock_get_conn):
        """Test getting entities when none exist"""
        mock_conn = Mock()
        mock_result = Mock()
        mock_result.has_next.return_value = False

        mock_conn.execute.return_value = mock_result
        mock_get_conn.return_value = mock_conn

        result = get_entities_by_chunk_id("chunk123")

        assert result == []


class TestGetRelatedEntitiesMulti:
    """Test getting related entities for multiple entities"""

    @patch("services.graph_service.get_kuzu_connection")
    def test_get_related_entities(self, mock_get_conn):
        """Test getting related entities"""
        mock_conn = Mock()

        # Mock results for first entity
        mock_result1 = Mock()
        rows1 = [("Related A", "PERSON", 1), ("Related B", "ORG", 2)]
        mock_result1.has_next.side_effect = [True, True, False]
        mock_result1.get_next.side_effect = rows1

        mock_conn.execute.return_value = mock_result1
        mock_get_conn.return_value = mock_conn

        result = get_related_entities_multi(["Entity 1"], depth=1)

        assert len(result) >= 2


class TestGetChunksByEntityNames:
    """Test getting chunks by entity names"""

    @patch("services.graph_service.get_kuzu_connection")
    def test_get_chunks(self, mock_get_conn):
        """Test getting chunks for entities"""
        mock_conn = Mock()
        mock_result = Mock()

        rows = [
            ("chunk1", "Content 1"),
            ("chunk2", "Content 2"),
        ]
        mock_result.has_next.side_effect = [True, True, False]
        mock_result.get_next.side_effect = rows

        mock_conn.execute.return_value = mock_result
        mock_get_conn.return_value = mock_conn

        result = get_chunks_by_entity_names(["Entity 1", "Entity 2"], limit=10)

        assert len(result) == 2
        assert result[0]["id"] == "chunk1"
        assert result[1]["id"] == "chunk2"

    @patch("services.graph_service.get_kuzu_connection")
    def test_get_chunks_empty_list(self, mock_get_conn):
        """Test with empty entity list"""
        result = get_chunks_by_entity_names([], limit=10)

        assert result == []

    @patch("services.graph_service.get_kuzu_connection")
    def test_get_chunks_error_handling(self, mock_get_conn):
        """Test error handling"""
        mock_conn = Mock()
        mock_conn.execute.side_effect = Exception("Error")
        mock_get_conn.return_value = mock_conn

        result = get_chunks_by_entity_names(["Entity 1"], limit=10)

        assert result == []
