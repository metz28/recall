"""
Text chunking service
"""

from core.config import settings


def chunk_text(text: str, chunk_size: int = None, overlap: int = None) -> list[str]:
    """
    Split text into overlapping chunks

    Simple character-based chunking for MVP. Can be enhanced later with:
    - Sentence-aware chunking
    - Semantic chunking
    - Markdown-aware chunking
    """
    chunk_size = chunk_size or settings.chunk_size
    overlap = overlap or settings.chunk_overlap

    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = start + chunk_size
        chunk = text[start:end]

        # Try to break at sentence boundary if we're not at the end
        if end < text_length:
            # Look for sentence endings
            last_period = chunk.rfind(". ")
            last_newline = chunk.rfind("\n")
            last_break = max(last_period, last_newline)

            if last_break > chunk_size * 0.5:  # Only break if we're at least halfway
                chunk = chunk[: last_break + 1]
                end = start + last_break + 1

        if chunk.strip():
            chunks.append(chunk.strip())

        start = end - overlap

    return chunks
