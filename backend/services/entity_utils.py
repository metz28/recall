"""
Shared utility functions for entity extraction
"""
import re


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
    text: str,
    start_char: int | None = None,
    end_char: int | None = None,
    entity_name: str | None = None,
    context_window: int = 100,
) -> str:
    """
    Extract surrounding context for an entity mention

    Args:
        text: Full text content
        start_char: Start character position of entity (optional)
        end_char: End character position of entity (optional)
        entity_name: Name of the entity to find (used if start_char/end_char not provided)
        context_window: Number of characters to include on each side

    Returns:
        Context string with entity surrounded by context
    """
    # If positions not provided, find entity by name
    if start_char is None or end_char is None:
        if entity_name is None:
            return text[:200] if len(text) > 200 else text

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
