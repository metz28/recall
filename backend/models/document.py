"""
Document and chunk models
"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4


class DocumentMetadata(BaseModel):
    """Metadata for a source document"""
    id: UUID = Field(default_factory=uuid4)
    title: str
    source_type: str  # file, url, text
    source_path: Optional[str] = None
    file_type: Optional[str] = None
    file_size: Optional[int] = None
    num_chunks: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    tags: list[str] = []
    collection: Optional[str] = None  # For Phase 3: workspaces


class Chunk(BaseModel):
    """A chunk of text from a document"""
    id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    content: str
    chunk_index: int
    start_char: Optional[int] = None
    end_char: Optional[int] = None
    embedding: Optional[list[float]] = None

    class Config:
        arbitrary_types_allowed = True


class Entity(BaseModel):
    """An entity extracted from text"""
    id: UUID = Field(default_factory=uuid4)
    name: str
    entity_type: str  # PERSON, ORG, CONCEPT, etc.
    description: Optional[str] = None
    chunk_ids: list[UUID] = []


class Relationship(BaseModel):
    """A relationship between entities"""
    id: UUID = Field(default_factory=uuid4)
    source_entity_id: UUID
    target_entity_id: UUID
    relationship_type: str
    context: Optional[str] = None
    chunk_id: UUID
