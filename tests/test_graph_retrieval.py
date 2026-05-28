"""
Tests for graph retrieval service
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock

from services.graph_retrieval import (
    get_chunk_entities,
    get_chunks_by_entities,
    get_related_entities,
    calculate_entity_overlap,
    get_entity_graph_distance
)


@pytest.mark.asyncio
class TestGetChunkEntities:
    """Test getting entities for a chunk"""

    async def test_get_chunk_entities_basic(self):
        """Test getting entities for a chunk"""
        with patch("aiosqlite.connect") as mock_connect:
            mock_db = AsyncMock()
            mock_cursor = AsyncMock()
            mock_cursor.fetchall = AsyncMock(return_value=[
                ("Entity 1",),
                ("Entity 2",),
                ("Entity 3",)
            ])

            # Create async context manager for db.execute()
            mock_execute_ctx = AsyncMock()
            mock_execute_ctx.__aenter__ = AsyncMock(return_value=mock_cursor)
            mock_execute_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_db.execute = Mock(return_value=mock_execute_ctx)

            mock_connect.return_value.__aenter__.return_value = mock_db

            result = await get_chunk_entities("chunk123")

            assert len(result) == 3
            assert result == ["Entity 1", "Entity 2", "Entity 3"]

    async def test_get_chunk_entities_empty(self):
        """Test getting entities when chunk has none"""
        with patch("aiosqlite.connect") as mock_connect:
            mock_db = AsyncMock()
            mock_cursor = AsyncMock()
            mock_cursor.fetchall = AsyncMock(return_value=[])

            mock_execute_ctx = AsyncMock()
            mock_execute_ctx.__aenter__ = AsyncMock(return_value=mock_cursor)
            mock_execute_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_db.execute = Mock(return_value=mock_execute_ctx)

            mock_connect.return_value.__aenter__.return_value = mock_db

            result = await get_chunk_entities("chunk123")

            assert result == []

    async def test_get_chunk_entities_query_format(self):
        """Test that query is formatted correctly"""
        with patch("aiosqlite.connect") as mock_connect:
            mock_db = AsyncMock()
            mock_cursor = AsyncMock()
            mock_cursor.fetchall = AsyncMock(return_value=[])

            mock_execute_ctx = AsyncMock()
            mock_execute_ctx.__aenter__ = AsyncMock(return_value=mock_cursor)
            mock_execute_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_db.execute = Mock(return_value=mock_execute_ctx)

            mock_connect.return_value.__aenter__.return_value = mock_db

            await get_chunk_entities("chunk123")

            # Verify the query was called with correct chunk_id
            call_args = mock_db.execute.call_args[0]
            assert "chunk123" in call_args[1]


@pytest.mark.asyncio
class TestGetChunksByEntities:
    """Test getting chunks by entity names"""

    async def test_get_chunks_by_entities_basic(self):
        """Test getting chunks for entities"""
        with patch("aiosqlite.connect") as mock_connect:
            mock_db = AsyncMock()
            mock_cursor = AsyncMock()

            # Mock Row objects
            mock_row1 = {
                "id": "chunk1",
                "content": "Content 1",
                "chunk_index": 0,
                "document_id": "doc1",
                "document_title": "Doc 1",
                "entity_match_count": 2
            }
            mock_row2 = {
                "id": "chunk2",
                "content": "Content 2",
                "chunk_index": 1,
                "document_id": "doc2",
                "document_title": "Doc 2",
                "entity_match_count": 1
            }

            mock_cursor.fetchall = AsyncMock(return_value=[mock_row1, mock_row2])

            mock_execute_ctx = AsyncMock()
            mock_execute_ctx.__aenter__ = AsyncMock(return_value=mock_cursor)
            mock_execute_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_db.execute = Mock(return_value=mock_execute_ctx)

            mock_connect.return_value.__aenter__.return_value = mock_db

            result = await get_chunks_by_entities(
                ["Entity 1", "Entity 2"],
                limit=10
            )

            assert len(result) == 2
            assert result[0]["id"] == "chunk1"
            assert result[1]["id"] == "chunk2"

    async def test_get_chunks_empty_entity_list(self):
        """Test with empty entity list"""
        result = await get_chunks_by_entities([], limit=10)
        assert result == []

    async def test_get_chunks_with_exclusions(self):
        """Test getting chunks with exclusions"""
        with patch("aiosqlite.connect") as mock_connect:
            mock_db = AsyncMock()
            mock_cursor = AsyncMock()
            mock_cursor.fetchall = AsyncMock(return_value=[])

            mock_execute_ctx = AsyncMock()
            mock_execute_ctx.__aenter__ = AsyncMock(return_value=mock_cursor)
            mock_execute_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_db.execute = Mock(return_value=mock_execute_ctx)

            mock_connect.return_value.__aenter__.return_value = mock_db

            exclude_ids = {"chunk1", "chunk2"}
            result = await get_chunks_by_entities(
                ["Entity 1"],
                limit=10,
                exclude_chunk_ids=exclude_ids
            )

            # Verify exclusions were added to query
            call_args = mock_db.execute.call_args[0]
            assert "NOT IN" in call_args[0]

    async def test_get_chunks_with_collection_filter(self):
        """Test getting chunks with collection filter"""
        with patch("aiosqlite.connect") as mock_connect:
            mock_db = AsyncMock()
            mock_cursor = AsyncMock()
            mock_cursor.fetchall = AsyncMock(return_value=[])

            mock_execute_ctx = AsyncMock()
            mock_execute_ctx.__aenter__ = AsyncMock(return_value=mock_cursor)
            mock_execute_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_db.execute = Mock(return_value=mock_execute_ctx)

            mock_connect.return_value.__aenter__.return_value = mock_db

            result = await get_chunks_by_entities(
                ["Entity 1"],
                limit=10,
                collection="test_collection"
            )

            # Verify collection filter was added to query
            call_args = mock_db.execute.call_args[0]
            assert "collection" in call_args[0]
            assert "test_collection" in call_args[1]

    async def test_get_chunks_respects_limit(self):
        """Test that limit parameter is respected"""
        with patch("aiosqlite.connect") as mock_connect:
            mock_db = AsyncMock()
            mock_cursor = AsyncMock()
            mock_cursor.fetchall = AsyncMock(return_value=[])

            mock_execute_ctx = AsyncMock()
            mock_execute_ctx.__aenter__ = AsyncMock(return_value=mock_cursor)
            mock_execute_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_db.execute = Mock(return_value=mock_execute_ctx)

            mock_connect.return_value.__aenter__.return_value = mock_db

            await get_chunks_by_entities(["Entity 1"], limit=5)

            # Verify limit was added to query
            call_args = mock_db.execute.call_args[0]
            assert 5 in call_args[1]

    async def test_get_chunks_multiple_entities(self):
        """Test getting chunks for multiple entities"""
        with patch("aiosqlite.connect") as mock_connect:
            mock_db = AsyncMock()
            mock_cursor = AsyncMock()
            mock_cursor.fetchall = AsyncMock(return_value=[])

            mock_execute_ctx = AsyncMock()
            mock_execute_ctx.__aenter__ = AsyncMock(return_value=mock_cursor)
            mock_execute_ctx.__aexit__ = AsyncMock(return_value=None)
            mock_db.execute = Mock(return_value=mock_execute_ctx)

            mock_connect.return_value.__aenter__.return_value = mock_db

            entities = ["Entity 1", "Entity 2", "Entity 3"]
            await get_chunks_by_entities(entities, limit=10)

            # Verify all entities in query parameters
            call_args = mock_db.execute.call_args[0]
            params = call_args[1]
            assert "Entity 1" in params
            assert "Entity 2" in params
            assert "Entity 3" in params


@pytest.mark.asyncio
class TestGetRelatedEntities:
    """Test getting related entities via RELATES_TO"""

    async def test_get_related_entities_basic(self):
        """Test getting related entities"""
        with patch("services.graph_retrieval.get_kuzu_connection") as mock_get_conn:
            mock_conn = Mock()
            mock_result = Mock()

            rows = [
                ("Related Entity 1", "PERSON", 1),
                ("Related Entity 2", "ORG", 2),
            ]
            mock_result.has_next.side_effect = [True, True, False]
            mock_result.get_next.side_effect = rows

            mock_conn.execute.return_value = mock_result
            mock_get_conn.return_value = mock_conn

            result = await get_related_entities(["Entity 1"], depth=1)

            assert len(result) == 2
            assert result[0]["source_entity"] == "Entity 1"
            assert result[0]["related_entity"] == "Related Entity 1"
            assert result[0]["distance"] == 1

    async def test_get_related_entities_empty_list(self):
        """Test with empty entity list"""
        result = await get_related_entities([], depth=1)
        assert result == []

    async def test_get_related_entities_invalid_depth(self):
        """Test with invalid depth"""
        result = await get_related_entities(["Entity 1"], depth=0)
        assert result == []

    async def test_get_related_entities_multiple_sources(self):
        """Test getting related entities for multiple source entities"""
        with patch("services.graph_retrieval.get_kuzu_connection") as mock_get_conn:
            mock_conn = Mock()

            # Mock results for two entities
            mock_result1 = Mock()
            rows1 = [("Related A", "PERSON", 1)]
            mock_result1.has_next.side_effect = [True, False]
            mock_result1.get_next.side_effect = rows1

            mock_result2 = Mock()
            rows2 = [("Related B", "ORG", 1)]
            mock_result2.has_next.side_effect = [True, False]
            mock_result2.get_next.side_effect = rows2

            mock_conn.execute.side_effect = [mock_result1, mock_result2]
            mock_get_conn.return_value = mock_conn

            result = await get_related_entities(["Entity 1", "Entity 2"], depth=1)

            assert len(result) >= 2

    async def test_get_related_entities_with_depth(self):
        """Test getting related entities with different depths"""
        with patch("services.graph_retrieval.get_kuzu_connection") as mock_get_conn:
            mock_conn = Mock()
            mock_result = Mock()

            # Entities at different distances
            rows = [
                ("Close Entity", "PERSON", 1),
                ("Far Entity", "ORG", 2),
            ]
            mock_result.has_next.side_effect = [True, True, False]
            mock_result.get_next.side_effect = rows

            mock_conn.execute.return_value = mock_result
            mock_get_conn.return_value = mock_conn

            result = await get_related_entities(["Entity 1"], depth=2)

            # Should include entities at different distances
            assert any(e["distance"] == 1 for e in result)
            assert any(e["distance"] == 2 for e in result)

    async def test_get_related_entities_error_handling(self):
        """Test error handling for non-existent entities"""
        with patch("services.graph_retrieval.get_kuzu_connection") as mock_get_conn:
            mock_conn = Mock()
            mock_conn.execute.side_effect = Exception("Entity not found")
            mock_get_conn.return_value = mock_conn

            result = await get_related_entities(["Nonexistent"], depth=1)

            # Should return empty list on error
            assert result == []


@pytest.mark.asyncio
class TestCalculateEntityOverlap:
    """Test entity overlap calculation"""

    async def test_calculate_overlap_basic(self):
        """Test calculating overlap between two entity lists"""
        chunk_entities = ["Entity A", "Entity B", "Entity C"]
        query_entities = ["Entity B", "Entity C", "Entity D"]

        overlap = await calculate_entity_overlap(chunk_entities, query_entities)

        # Entity B and Entity C overlap
        assert overlap == 2

    async def test_calculate_overlap_no_overlap(self):
        """Test with no overlapping entities"""
        chunk_entities = ["Entity A", "Entity B"]
        query_entities = ["Entity C", "Entity D"]

        overlap = await calculate_entity_overlap(chunk_entities, query_entities)

        assert overlap == 0

    async def test_calculate_overlap_full_overlap(self):
        """Test with complete overlap"""
        entities = ["Entity A", "Entity B", "Entity C"]

        overlap = await calculate_entity_overlap(entities, entities)

        assert overlap == 3

    async def test_calculate_overlap_case_insensitive(self):
        """Test that overlap is case-insensitive"""
        chunk_entities = ["Entity A", "Entity B"]
        query_entities = ["entity a", "ENTITY B"]

        overlap = await calculate_entity_overlap(chunk_entities, query_entities)

        # Should match despite different cases
        assert overlap == 2

    async def test_calculate_overlap_empty_lists(self):
        """Test with empty lists"""
        overlap = await calculate_entity_overlap([], [])
        assert overlap == 0

        overlap = await calculate_entity_overlap(["Entity A"], [])
        assert overlap == 0

        overlap = await calculate_entity_overlap([], ["Entity A"])
        assert overlap == 0

    async def test_calculate_overlap_duplicates(self):
        """Test with duplicate entities in lists"""
        chunk_entities = ["Entity A", "Entity A", "Entity B"]
        query_entities = ["Entity A", "Entity B", "Entity B"]

        overlap = await calculate_entity_overlap(chunk_entities, query_entities)

        # Should count unique overlaps only
        assert overlap == 2


@pytest.mark.asyncio
class TestGetEntityGraphDistance:
    """Test calculating graph distance between entities"""

    async def test_get_distance_same_entity(self):
        """Test distance when entities are the same"""
        distance = await get_entity_graph_distance("Entity A", "Entity A")

        assert distance == 0

    async def test_get_distance_case_insensitive_same(self):
        """Test that same entity comparison is case-insensitive"""
        distance = await get_entity_graph_distance("Entity A", "entity a")

        assert distance == 0

    async def test_get_distance_connected_entities(self):
        """Test distance between connected entities"""
        with patch("services.graph_retrieval.get_kuzu_connection") as mock_get_conn:
            mock_conn = Mock()
            mock_result = Mock()

            # Distance of 2 hops
            mock_result.has_next.return_value = True
            mock_result.get_next.return_value = (2,)

            mock_conn.execute.return_value = mock_result
            mock_get_conn.return_value = mock_conn

            distance = await get_entity_graph_distance("Entity A", "Entity B", max_depth=3)

            assert distance == 2

    async def test_get_distance_not_connected(self):
        """Test distance when entities are not connected"""
        with patch("services.graph_retrieval.get_kuzu_connection") as mock_get_conn:
            mock_conn = Mock()
            mock_result = Mock()
            mock_result.has_next.return_value = False

            mock_conn.execute.return_value = mock_result
            mock_get_conn.return_value = mock_conn

            distance = await get_entity_graph_distance("Entity A", "Entity B", max_depth=3)

            assert distance is None

    async def test_get_distance_error_handling(self):
        """Test error handling"""
        with patch("services.graph_retrieval.get_kuzu_connection") as mock_get_conn:
            mock_conn = Mock()
            mock_conn.execute.side_effect = Exception("Graph error")
            mock_get_conn.return_value = mock_conn

            distance = await get_entity_graph_distance("Entity A", "Entity B")

            # Should return None on error
            assert distance is None

    async def test_get_distance_respects_max_depth(self):
        """Test that max_depth parameter is used in query"""
        with patch("services.graph_retrieval.get_kuzu_connection") as mock_get_conn:
            mock_conn = Mock()
            mock_result = Mock()
            mock_result.has_next.return_value = False

            mock_conn.execute.return_value = mock_result
            mock_get_conn.return_value = mock_conn

            await get_entity_graph_distance("Entity A", "Entity B", max_depth=5)

            # Verify max_depth is in the query
            call_args = mock_conn.execute.call_args[0]
            assert "1..5" in call_args[0]  # Should be in path length spec

    async def test_get_distance_direct_connection(self):
        """Test distance for directly connected entities"""
        with patch("services.graph_retrieval.get_kuzu_connection") as mock_get_conn:
            mock_conn = Mock()
            mock_result = Mock()

            # Direct connection (distance 1)
            mock_result.has_next.return_value = True
            mock_result.get_next.return_value = (1,)

            mock_conn.execute.return_value = mock_result
            mock_get_conn.return_value = mock_conn

            distance = await get_entity_graph_distance("Entity A", "Entity B")

            assert distance == 1
