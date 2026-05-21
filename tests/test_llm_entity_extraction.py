"""
Tests for LLM-based entity extraction
"""

import pytest
from unittest.mock import patch, MagicMock

from services.llm_entity_extraction import (
    extract_entities_from_text_llm,
    extract_entities_batch_llm,
    normalize_entity_name,
    get_entity_context,
)


def test_normalize_entity_name():
    """Test entity name normalization"""
    assert normalize_entity_name("john smith") == "John Smith"
    assert normalize_entity_name("  ACME  Corp  ") == "Acme Corp"
    assert normalize_entity_name("new\n\nyork") == "New York"


def test_get_entity_context():
    """Test context extraction"""
    text = "This is a long piece of text about John Smith who works at ACME Corporation in New York City."

    context = get_entity_context(text, "John Smith", context_window=20)
    assert "John Smith" in context
    assert len(context) <= 60  # entity + 2*20 + some buffer

    # Test entity not found
    context = get_entity_context(text, "NonExistent", context_window=50)
    assert len(context) > 0  # Should return start of text


@pytest.mark.asyncio
@patch("services.llm_entity_extraction.anthropic.Anthropic")
async def test_extract_entities_from_text_llm_success(mock_anthropic_class):
    """Test successful LLM entity extraction"""
    # Mock the Anthropic client
    mock_client = MagicMock()
    mock_anthropic_class.return_value = mock_client

    # Mock response
    mock_message = MagicMock()
    mock_message.content = [
        MagicMock(
            text='[{"name": "John Smith", "type": "PERSON"}, {"name": "ACME Corp", "type": "ORG"}]'
        )
    ]
    mock_client.messages.create.return_value = mock_message

    # Set API key in settings
    with patch("services.llm_entity_extraction.settings") as mock_settings:
        mock_settings.anthropic_api_key = "test-key"

        text = "John Smith works at ACME Corp in New York."
        entities = extract_entities_from_text_llm(
            text, entity_types={"PERSON", "ORG", "GPE"}
        )

        assert len(entities) == 2
        assert entities[0]["name"] == "John Smith"
        assert entities[0]["type"] == "PERSON"
        assert entities[0]["normalized_name"] == "John Smith"
        assert entities[1]["name"] == "ACME Corp"
        assert entities[1]["type"] == "ORG"


@pytest.mark.asyncio
@patch("services.llm_entity_extraction.anthropic.Anthropic")
async def test_extract_entities_from_text_llm_with_markdown(mock_anthropic_class):
    """Test LLM extraction with markdown-wrapped response"""
    mock_client = MagicMock()
    mock_anthropic_class.return_value = mock_client

    # Mock response with markdown code blocks
    mock_message = MagicMock()
    mock_message.content = [
        MagicMock(
            text='```json\n[{"name": "Tesla", "type": "ORG"}]\n```'
        )
    ]
    mock_client.messages.create.return_value = mock_message

    with patch("services.llm_entity_extraction.settings") as mock_settings:
        mock_settings.anthropic_api_key = "test-key"

        text = "Tesla is an electric vehicle company."
        entities = extract_entities_from_text_llm(text)

        assert len(entities) == 1
        assert entities[0]["name"] == "Tesla"
        assert entities[0]["type"] == "ORG"


@pytest.mark.asyncio
@patch("services.llm_entity_extraction.anthropic.Anthropic")
async def test_extract_entities_batch_llm(mock_anthropic_class):
    """Test batch LLM entity extraction"""
    mock_client = MagicMock()
    mock_anthropic_class.return_value = mock_client

    # Mock responses for multiple texts
    mock_message_1 = MagicMock()
    mock_message_1.content = [MagicMock(text='[{"name": "Alice", "type": "PERSON"}]')]

    mock_message_2 = MagicMock()
    mock_message_2.content = [MagicMock(text='[{"name": "Google", "type": "ORG"}]')]

    mock_client.messages.create.side_effect = [mock_message_1, mock_message_2]

    with patch("services.llm_entity_extraction.settings") as mock_settings:
        mock_settings.anthropic_api_key = "test-key"

        texts = ["Alice is a developer.", "Google is a tech company."]
        results = extract_entities_batch_llm(texts)

        assert len(results) == 2
        assert len(results[0]) == 1
        assert results[0][0]["name"] == "Alice"
        assert len(results[1]) == 1
        assert results[1][0]["name"] == "Google"


@pytest.mark.asyncio
async def test_extract_entities_no_api_key():
    """Test that extraction fails gracefully without API key"""
    with patch("services.llm_entity_extraction.settings") as mock_settings:
        mock_settings.anthropic_api_key = None

        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY not set"):
            extract_entities_from_text_llm("Some text")


@pytest.mark.asyncio
@patch("services.llm_entity_extraction.anthropic.Anthropic")
async def test_extract_entities_invalid_json(mock_anthropic_class):
    """Test handling of invalid JSON response"""
    mock_client = MagicMock()
    mock_anthropic_class.return_value = mock_client

    # Mock invalid JSON response
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="This is not valid JSON")]
    mock_client.messages.create.return_value = mock_message

    with patch("services.llm_entity_extraction.settings") as mock_settings:
        mock_settings.anthropic_api_key = "test-key"

        text = "Some text"
        entities = extract_entities_from_text_llm(text)

        # Should return empty list on error
        assert entities == []


@pytest.mark.asyncio
@patch("services.llm_entity_extraction.anthropic.Anthropic")
async def test_extract_entities_filters_types(mock_anthropic_class):
    """Test that entity type filtering works"""
    mock_client = MagicMock()
    mock_anthropic_class.return_value = mock_client

    # Mock response with multiple types
    mock_message = MagicMock()
    mock_message.content = [
        MagicMock(
            text='[{"name": "Alice", "type": "PERSON"}, {"name": "Google", "type": "ORG"}, {"name": "New York", "type": "GPE"}]'
        )
    ]
    mock_client.messages.create.return_value = mock_message

    with patch("services.llm_entity_extraction.settings") as mock_settings:
        mock_settings.anthropic_api_key = "test-key"

        text = "Alice works at Google in New York."
        # Only request PERSON entities
        entities = extract_entities_from_text_llm(text, entity_types={"PERSON"})

        # Should only return PERSON entities
        assert len(entities) == 1
        assert entities[0]["type"] == "PERSON"
