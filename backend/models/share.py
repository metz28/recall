"""
Pydantic models for shareable links
"""
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field


class ShareCreate(BaseModel):
    """Request to create a shareable link"""
    resource_type: Literal["document", "search", "collection"]
    resource_id: Optional[str] = None  # Required for document/collection, None for search
    expires_in_days: Optional[int] = None  # None = never expires
    access_level: Literal["view"] = "view"  # Future: could add "edit", "comment"
    metadata: Optional[dict] = None  # For search: query params, filters, etc.


class ShareResponse(BaseModel):
    """Response when creating/retrieving a share"""
    id: str
    token: str
    resource_type: str
    resource_id: Optional[str]
    owner_id: str
    created_at: datetime
    expires_at: Optional[datetime]
    access_level: str
    is_active: bool
    metadata: Optional[dict]
    view_count: int
    last_accessed: Optional[datetime]
    share_url: str  # Full URL to access the shared resource


class ShareList(BaseModel):
    """List of shares owned by a user"""
    shares: list[ShareResponse]


class ShareMetadata(BaseModel):
    """Metadata about a shared resource (public access)"""
    resource_type: str
    resource_title: Optional[str]  # Document title or search query
    owner_username: str
    created_at: datetime
    expires_at: Optional[datetime]
    is_active: bool
    is_expired: bool


class SharedDocumentResponse(BaseModel):
    """Response for accessing a shared document"""
    id: str
    title: str
    file_type: Optional[str]
    num_chunks: int
    created_at: datetime
    tags: Optional[list[str]]
    collection: Optional[str]
    # Note: We don't expose source_path or user_id for security


class SharedSearchResponse(BaseModel):
    """Response for accessing a shared search"""
    query: str
    results: list[dict]  # Search results
    total_results: int
    collection: Optional[str]
    tags: Optional[list[str]]
