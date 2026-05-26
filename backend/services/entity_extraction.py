"""
Entity extraction service using spaCy
"""

from functools import lru_cache

import spacy

from core.logging_config import get_logger
from .entity_utils import normalize_entity_name, get_entity_context

logger = get_logger(__name__)


# Entity types to extract
DEFAULT_ENTITY_TYPES = {
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


@lru_cache(maxsize=1)
def get_spacy_model(model_name: str = "en_core_web_sm"):
    """Load and cache the spaCy model"""
    logger.info(f"Loading spaCy model: {model_name}")
    try:
        nlp = spacy.load(model_name)
        logger.info(f"spaCy model '{model_name}' loaded")
        return nlp
    except OSError:
        logger.error(
            f"Model '{model_name}' not found. Run: python -m spacy download {model_name}"
        )
        raise


def extract_entities_from_text(
    text: str,
    entity_types: set = None,
    model_name: str = "en_core_web_sm",
    context_window: int = 100,
) -> list[dict]:
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
            context = get_entity_context(
                text, start_char=ent.start_char, end_char=ent.end_char, context_window=context_window
            )

            entities.append(
                {
                    "name": ent.text,
                    "normalized_name": normalize_entity_name(ent.text),
                    "type": ent.label_,
                    "start": ent.start_char,
                    "end": ent.end_char,
                    "context": context,
                }
            )

    return entities


def extract_entities_batch(
    texts: list[str],
    entity_types: set = None,
    model_name: str = "en_core_web_sm",
    context_window: int = 100,
    batch_size: int = 50,
) -> list[list[dict]]:
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
                context = get_entity_context(
                    text, ent.start_char, ent.end_char, context_window
                )

                entities.append(
                    {
                        "name": ent.text,
                        "normalized_name": normalize_entity_name(ent.text),
                        "type": ent.label_,
                        "start": ent.start_char,
                        "end": ent.end_char,
                        "context": context,
                    }
                )

        all_entities.append(entities)

    return all_entities


def deduplicate_entities(entity_mentions: list[dict]) -> dict[str, dict]:
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
                "variants": set(),
            }

        # Update entity info
        entity = entities_map[norm_name]
        entity["mention_count"] += 1
        entity["variants"].add(mention["name"])

    # Convert variants set to list
    for entity in entities_map.values():
        entity["variants"] = list(entity["variants"])

    return entities_map
