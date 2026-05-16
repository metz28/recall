"""
Entity extraction service using spaCy
"""
import spacy
from functools import lru_cache
from typing import List, Dict, Tuple
import re


# Entity types to extract
DEFAULT_ENTITY_TYPES = {
    "PERSON", "ORG", "GPE", "PRODUCT", "EVENT",
    "WORK_OF_ART", "LAW", "NORP", "FAC"
}


@lru_cache(maxsize=1)
def get_spacy_model(model_name: str = "en_core_web_sm"):
    """Load and cache the spaCy model"""
    print(f"Loading spaCy model: {model_name}")
    try:
        nlp = spacy.load(model_name)
        print(f"✅ spaCy model '{model_name}' loaded")
        return nlp
    except OSError:
        print(f"⚠️  Model '{model_name}' not found. Run: python -m spacy download {model_name}")
        raise


def normalize_entity_name(name: str) -> str:
    """
    Normalize entity name for deduplication
    - Strip whitespace
    - Convert to title case for consistency
    - Remove extra spaces
    """
    # Strip and normalize whitespace
    normalized = re.sub(r'\s+', ' ', name.strip())
    # Convert to title case for consistency
    normalized = normalized.title()
    return normalized


def get_entity_context(text: str, start_char: int, end_char: int, context_window: int = 100) -> str:
    """
    Extract surrounding context for an entity mention

    Args:
        text: Full text content
        start_char: Start character position of entity
        end_char: End character position of entity
        context_window: Number of characters to include on each side

    Returns:
        Context string with entity surrounded by context
    """
    # Get surrounding context
    context_start = max(0, start_char - context_window)
    context_end = min(len(text), end_char + context_window)

    context = text[context_start:context_end]

    # Clean up context (remove leading/trailing partial words)
    if context_start > 0:
        # Find first space to avoid partial word
        first_space = context.find(' ')
        if first_space != -1:
            context = context[first_space + 1:]

    if context_end < len(text):
        # Find last space to avoid partial word
        last_space = context.rfind(' ')
        if last_space != -1:
            context = context[:last_space]

    return context.strip()


def extract_entities_from_text(
    text: str,
    entity_types: set = None,
    model_name: str = "en_core_web_sm",
    context_window: int = 100
) -> List[Dict]:
    """
    Extract entities from a single text

    Args:
        text: Text to extract entities from
        entity_types: Set of entity types to extract (defaults to DEFAULT_ENTITY_TYPES)
        model_name: spaCy model to use
        context_window: Number of characters for context extraction

    Returns:
        List of entity dictionaries with keys: name, type, start, end, context
    """
    if entity_types is None:
        entity_types = DEFAULT_ENTITY_TYPES

    nlp = get_spacy_model(model_name)
    doc = nlp(text)

    entities = []
    for ent in doc.ents:
        if ent.label_ in entity_types:
            context = get_entity_context(text, ent.start_char, ent.end_char, context_window)

            entities.append({
                "name": ent.text,
                "normalized_name": normalize_entity_name(ent.text),
                "type": ent.label_,
                "start": ent.start_char,
                "end": ent.end_char,
                "context": context
            })

    return entities


def extract_entities_batch(
    texts: List[str],
    entity_types: set = None,
    model_name: str = "en_core_web_sm",
    context_window: int = 100,
    batch_size: int = 50
) -> List[List[Dict]]:
    """
    Extract entities from multiple texts using batch processing

    Args:
        texts: List of texts to process
        entity_types: Set of entity types to extract
        model_name: spaCy model to use
        context_window: Number of characters for context extraction
        batch_size: Number of texts to process in each batch

    Returns:
        List of entity lists (one per input text, maintaining order)
    """
    if entity_types is None:
        entity_types = DEFAULT_ENTITY_TYPES

    if not texts:
        return []

    nlp = get_spacy_model(model_name)

    # Process in batches using nlp.pipe for efficiency
    all_entities = []

    # Use nlp.pipe for batch processing
    for text, doc in zip(texts, nlp.pipe(texts, batch_size=batch_size)):
        entities = []
        for ent in doc.ents:
            if ent.label_ in entity_types:
                context = get_entity_context(text, ent.start_char, ent.end_char, context_window)

                entities.append({
                    "name": ent.text,
                    "normalized_name": normalize_entity_name(ent.text),
                    "type": ent.label_,
                    "start": ent.start_char,
                    "end": ent.end_char,
                    "context": context
                })

        all_entities.append(entities)

    return all_entities


def deduplicate_entities(entity_mentions: List[Dict]) -> Dict[str, Dict]:
    """
    Deduplicate entities across mentions

    Args:
        entity_mentions: List of entity mention dictionaries

    Returns:
        Dictionary mapping normalized_name -> entity info with aggregated data
    """
    entities_map = {}

    for mention in entity_mentions:
        norm_name = mention["normalized_name"]

        if norm_name not in entities_map:
            entities_map[norm_name] = {
                "normalized_name": norm_name,
                "canonical_name": mention["name"],  # Use first occurrence as canonical
                "type": mention["type"],
                "mention_count": 0,
                "variants": set()
            }

        # Update entity info
        entity = entities_map[norm_name]
        entity["mention_count"] += 1
        entity["variants"].add(mention["name"])

    # Convert variants set to list
    for entity in entities_map.values():
        entity["variants"] = list(entity["variants"])

    return entities_map
