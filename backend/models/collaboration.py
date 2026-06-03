"""
Pydantic models for multi-user collaboration
"""
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel


class PermissionLevel(str):
    """Permission levels for collaboration"""
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"
    OWNER = "owner"


class CollaboratorAdd(BaseModel):
    """Request to add a collaborator"""
    resource_type: Literal["document", "collection"]
    resource_id: str
    collaborator_email: str  # Email of user to add
    permission: Literal["read", "write", "admin"]
    message: Optional[str] = None  # Optional message to collaborator


class CollaboratorUpdate(BaseModel):
    """Request to update collaborator permissions"""
    permission: Literal["read", "write", "admin"]


class CollaboratorResponse(BaseModel):
    """Response with collaborator information"""
    id: str
    resource_type: str
    resource_id: str
    resource_title: Optional[str]
    collaborator_id: str
    collaborator_email: str
    collaborator_username: str
    permission: str
    added_by: str
    added_at: datetime
    last_accessed: Optional[datetime]


class CollaboratorList(BaseModel):
    """List of collaborators"""
    collaborators: list[CollaboratorResponse]


class SharedWithMeResponse(BaseModel):
    """Documents/collections shared with current user"""
    id: str
    resource_type: str
    resource_id: str
    resource_title: str
    owner_email: str
    owner_username: str
    permission: str
    added_at: datetime
    last_accessed: Optional[datetime]


class SharedWithMeList(BaseModel):
    """List of resources shared with user"""
    shared_items: list[SharedWithMeResponse]


class ActivityLogEntry(BaseModel):
    """Single activity log entry"""
    id: str
    resource_type: str
    resource_id: str
    user_id: str
    username: str
    action: str  # "created", "edited", "deleted", "shared", "commented", etc.
    details: Optional[str]
    created_at: datetime


class ActivityLogResponse(BaseModel):
    """Activity log for a resource"""
    activities: list[ActivityLogEntry]
    total: int


class CollaborationStats(BaseModel):
    """Statistics about collaboration"""
    total_shared_by_me: int
    total_shared_with_me: int
    total_collaborators: int
    recent_activity_count: int
