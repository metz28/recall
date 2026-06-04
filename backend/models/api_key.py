"""API Key models for programmatic access."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ApiKeyCreate(BaseModel):
    """Request to create a new API key."""
    name: str = Field(..., min_length=1, max_length=100, description="User-friendly name for the API key")
    expires_at: Optional[datetime] = Field(None, description="Optional expiration date")


class ApiKeyResponse(BaseModel):
    """API key information (without full key)."""
    id: str
    name: str
    key_prefix: str  # First 16 chars for display (e.g., "recall_sk_prod_a")
    created_at: datetime
    last_used_at: Optional[datetime]
    expires_at: Optional[datetime]
    is_active: bool


class ApiKeyCreateResponse(BaseModel):
    """Response when creating a new API key (includes full key once)."""
    id: str
    name: str
    api_key: str  # Full key shown only once
    key_prefix: str
    created_at: datetime
    expires_at: Optional[datetime]
    is_active: bool
    warning: str = "Save this API key now. You won't be able to see it again."


class ApiKeyList(BaseModel):
    """List of API keys."""
    api_keys: list[ApiKeyResponse]
    total: int


class ApiKeyToggle(BaseModel):
    """Request to toggle API key active status."""
    is_active: bool
