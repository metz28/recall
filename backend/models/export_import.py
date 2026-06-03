"""
Pydantic models for export/import functionality
"""
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel


class DocumentExport(BaseModel):
    """Full document export with all metadata"""
    id: str
    title: str
    source_type: str
    source_path: Optional[str]
    file_type: Optional[str]
    file_size: Optional[int]
    num_chunks: int
    created_at: datetime
    updated_at: datetime
    collection: Optional[str]
    tags: Optional[list[str]]
    chunks: list[dict]  # List of {id, content, chunk_index}
    entities: Optional[list[dict]]  # List of entities mentioned
    relationships: Optional[list[dict]]  # List of relationships


class ExportRequest(BaseModel):
    """Request to export data"""
    export_type: Literal["document", "collection", "all"]
    resource_id: Optional[str] = None  # Required for document/collection, None for "all"
    include_embeddings: bool = False  # Whether to include vector embeddings (makes file large)
    include_graph: bool = True  # Whether to include entities and relationships
    format: Literal["json"] = "json"  # Future: could add "zip", "csv", etc.


class ExportResponse(BaseModel):
    """Response with export data or download info"""
    export_type: str
    total_documents: int
    total_chunks: int
    total_entities: Optional[int]
    total_relationships: Optional[int]
    created_at: datetime
    data: Optional[dict] = None  # For direct JSON response
    download_url: Optional[str] = None  # For file downloads (future)


class ImportRequest(BaseModel):
    """Request to import data"""
    data: dict  # The exported JSON data
    import_mode: Literal["skip", "replace", "merge"] = "skip"  # How to handle existing documents
    regenerate_embeddings: bool = True  # Whether to regenerate embeddings
    target_collection: Optional[str] = None  # Optional: override collection on import


class ImportResponse(BaseModel):
    """Response after import"""
    total_documents: int
    imported_documents: int
    skipped_documents: int
    replaced_documents: int
    total_chunks: int
    total_entities: Optional[int]
    total_relationships: Optional[int]
    errors: list[str]
    completed_at: datetime
