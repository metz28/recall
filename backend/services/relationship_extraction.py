"""
Relationship extraction service using LLM
"""

import json
import re
from typing import Optional

import anthropic

from core.config import settings


def extract_relationships_from_entities_llm(
    text: str,
    entities: list[dict],
    model_name: str = "claude-3-haiku-20240307",
) -> list[dict]:
    """
    Extract relationships between entities in a text using Claude LLM

    Args:
        text: Text content containing the entities
        entities: List of entity dictionaries with keys: name, type
        model_name: Claude model to use

    Returns:
        List of relationship dictionaries with keys: source_entity, target_entity, relationship_type, context
    """
    if not settings.anthropic_api_key:
        raise ValueError(
            "ANTHROPIC_API_KEY not set. Please set it in .env file or environment."
        )

    # Need at least 2 entities to have a relationship
    if len(entities) < 2:
        return []

    # Format entities for the prompt
    entity_list = [
        f"- {e['normalized_name']} ({e['type']})" for e in entities
    ]
    entity_names = ", ".join([e['normalized_name'] for e in entities])

    # Create prompt for Claude
    prompt = f"""Extract relationships between the following entities found in the text. Return ONLY a JSON array with no additional text or markdown formatting.

Entities found:
{chr(10).join(entity_list)}

Text to analyze:
{text}

Identify meaningful relationships between these entities. For each relationship, determine:
- source_entity: The entity initiating or being described
- target_entity: The entity being related to
- relationship_type: The type of relationship (e.g., "works_for", "located_in", "created_by", "part_of", "associated_with", "competitor_of", "owns", "manages", "founded")
- context: A brief phrase from the text describing this relationship

Only include relationships that are clearly stated or strongly implied in the text.

Return a JSON array in this exact format:
[{{"source_entity": "Entity Name", "target_entity": "Entity Name", "relationship_type": "relationship_type", "context": "relevant text snippet"}}, ...]

Return an empty array [] if no relationships are found."""

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
        relationships_data = json.loads(response_text)

        if not isinstance(relationships_data, list):
            print(f"⚠️  LLM returned non-list response: {response_text[:100]}")
            return []

        # Validate and normalize relationships
        relationships = []
        entity_names_set = {e['normalized_name'].lower() for e in entities}

        for item in relationships_data:
            if not isinstance(item, dict):
                continue

            required_keys = {"source_entity", "target_entity", "relationship_type"}
            if not all(key in item for key in required_keys):
                continue

            source = item["source_entity"].strip()
            target = item["target_entity"].strip()
            rel_type = item["relationship_type"].strip().lower()
            context = item.get("context", "")[:300]  # Limit context length

            # Validate entities exist in our list
            if source.lower() not in entity_names_set or target.lower() not in entity_names_set:
                continue

            # Skip self-relationships
            if source.lower() == target.lower():
                continue

            relationships.append(
                {
                    "source_entity": source,
                    "target_entity": target,
                    "relationship_type": rel_type,
                    "context": context,
                }
            )

        return relationships

    except json.JSONDecodeError as e:
        print(f"⚠️  Failed to parse LLM response as JSON: {e}")
        print(f"Response was: {response_text[:200]}")
        return []
    except Exception as e:
        print(f"⚠️  LLM relationship extraction failed: {e}")
        return []


def extract_relationships_batch_llm(
    chunks: list[str],
    chunk_entities: list[list[dict]],
    model_name: str = "claude-3-haiku-20240307",
) -> list[list[dict]]:
    """
    Extract relationships from multiple chunks

    Args:
        chunks: List of text chunks
        chunk_entities: List of entity lists (one per chunk)
        model_name: Claude model to use

    Returns:
        List of relationship lists (one per chunk)
    """
    if not chunks or not chunk_entities:
        return []

    if len(chunks) != len(chunk_entities):
        raise ValueError("chunks and chunk_entities must have the same length")

    all_relationships = []

    # Process each chunk
    for chunk, entities in zip(chunks, chunk_entities):
        if len(entities) >= 2:  # Need at least 2 entities
            relationships = extract_relationships_from_entities_llm(
                chunk,
                entities,
                model_name=model_name,
            )
            all_relationships.append(relationships)
        else:
            all_relationships.append([])

    return all_relationships


def normalize_relationship_type(rel_type: str) -> str:
    """
    Normalize relationship type for consistency

    Args:
        rel_type: Raw relationship type

    Returns:
        Normalized relationship type
    """
    # Convert to lowercase and replace spaces with underscores
    normalized = rel_type.lower().strip()
    normalized = re.sub(r"\s+", "_", normalized)
    # Remove special characters except underscores
    normalized = re.sub(r"[^\w_]", "", normalized)
    return normalized
