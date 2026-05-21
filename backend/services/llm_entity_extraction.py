"""
LLM-based entity extraction service using Claude
"""

import json
import re
from typing import Optional

import anthropic

from core.config import settings


def normalize_entity_name(name: str) -> str:
    """
    Normalize entity name for deduplication
    - Strip whitespace
    - Convert to title case for consistency
    - Remove extra spaces
    """
    normalized = re.sub(r"\s+", " ", name.strip())
    normalized = normalized.title()
    return normalized


def get_entity_context(
    text: str, entity_name: str, context_window: int = 100
) -> str:
    """
    Extract surrounding context for an entity mention

    Args:
        text: Full text content
        entity_name: Name of the entity to find
        context_window: Number of characters to include on each side

    Returns:
        Context string with entity surrounded by context
    """
    # Find entity position in text (case-insensitive)
    pattern = re.compile(re.escape(entity_name), re.IGNORECASE)
    match = pattern.search(text)

    if not match:
        return text[:200] if len(text) > 200 else text

    start_char = match.start()
    end_char = match.end()

    # Get surrounding context
    context_start = max(0, start_char - context_window)
    context_end = min(len(text), end_char + context_window)

    context = text[context_start:context_end]

    # Clean up context (remove leading/trailing partial words)
    if context_start > 0:
        first_space = context.find(" ")
        if first_space != -1:
            context = context[first_space + 1 :]

    if context_end < len(text):
        last_space = context.rfind(" ")
        if last_space != -1:
            context = context[:last_space]

    return context.strip()


def extract_entities_from_text_llm(
    text: str,
    entity_types: Optional[set] = None,
    model_name: str = "claude-3-haiku-20240307",
    context_window: int = 100,
) -> list[dict]:
    """
    Extract entities from text using Claude LLM

    Args:
        text: Text to extract entities from
        entity_types: Set of entity types to extract
        model_name: Claude model to use
        context_window: Number of characters for context extraction

    Returns:
        List of entity dictionaries with keys: name, type, context
    """
    if not settings.anthropic_api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY not set. Please set it in .env file or environment."
        )

    if entity_types is None:
        entity_types = {
            "PERSON",
            "ORG",
            "GPE",
            "PRODUCT",
            "EVENT",
            "WORK_OF_ART",
            "LAW",
            "NORP",
            "FAC",
        }

    # Convert entity types to readable format
    entity_types_str = ", ".join(sorted(entity_types))

    # Create prompt for Claude
    prompt = f"""Extract all named entities from the following text. Return ONLY a JSON array with no additional text or markdown formatting.

Entity types to extract: {entity_types_str}

Entity type descriptions:
- PERSON: People, including fictional characters
- ORG: Organizations, companies, agencies, institutions
- GPE: Geopolitical entities (countries, cities, states)
- PRODUCT: Products, services, brands
- EVENT: Named events (conferences, battles, sports events)
- WORK_OF_ART: Titles of books, songs, movies, paintings
- LAW: Named laws, acts, legal documents
- NORP: Nationalities, religious or political groups
- FAC: Facilities (buildings, airports, highways, bridges)

Text to analyze:
{text}

Return a JSON array in this exact format:
[{{"name": "Entity Name", "type": "ENTITY_TYPE"}}, ...]

Only include entities that clearly match the types above. Return an empty array [] if no entities are found."""

    try:
        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

        message = client.messages.create(
            model=model_name,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )

        # Extract text response
        response_text = message.content[0].text.strip()

        # Remove markdown code blocks if present
        response_text = re.sub(r"```json\s*", "", response_text)
        response_text = re.sub(r"```\s*$", "", response_text)
        response_text = response_text.strip()

        # Parse JSON response
        entities_data = json.loads(response_text)

        if not isinstance(entities_data, list):
            print(f"⚠️  LLM returned non-list response: {response_text[:100]}")
            return []

        # Format entities with context
        entities = []
        seen_entities = set()  # Deduplicate within same text

        for item in entities_data:
            if not isinstance(item, dict) or "name" not in item or "type" not in item:
                continue

            name = item["name"].strip()
            entity_type = item["type"].strip().upper()

            # Skip if entity type not in requested types
            if entity_type not in entity_types:
                continue

            # Skip duplicates within same text
            entity_key = (normalize_entity_name(name), entity_type)
            if entity_key in seen_entities:
                continue
            seen_entities.add(entity_key)

            # Extract context
            context = get_entity_context(text, name, context_window)

            entities.append(
                {
                    "name": name,
                    "normalized_name": normalize_entity_name(name),
                    "type": entity_type,
                    "start": 0,  # LLM doesn't provide exact positions
                    "end": 0,
                    "context": context,
                }
            )

        return entities

    except json.JSONDecodeError as e:
        print(f"⚠️  Failed to parse LLM response as JSON: {e}")
        print(f"Response was: {response_text[:200]}")
        return []
    except Exception as e:
        print(f"⚠️  LLM entity extraction failed: {e}")
        return []


def extract_entities_batch_llm(
    texts: list[str],
    entity_types: Optional[set] = None,
    model_name: str = "claude-3-haiku-20240307",
    context_window: int = 100,
) -> list[list[dict]]:
    """
    Extract entities from multiple texts using Claude LLM

    Args:
        texts: List of texts to process
        entity_types: Set of entity types to extract
        model_name: Claude model to use
        context_window: Number of characters for context extraction

    Returns:
        List of entity lists (one per input text)
    """
    if not texts:
        return []

    all_entities = []

    # Process each text individually
    # Note: Could be optimized with batching in future
    for text in texts:
        entities = extract_entities_from_text_llm(
            text,
            entity_types=entity_types,
            model_name=model_name,
            context_window=context_window,
        )
        all_entities.append(entities)

    return all_entities
