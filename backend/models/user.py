"""User models for authentication."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    """Base user model with common fields."""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)


class UserCreate(UserBase):
    """User creation model with password."""
    password: str = Field(..., min_length=8)


class UserResponse(UserBase):
    """User response model (no password)."""
    id: str
    created_at: datetime
    is_active: bool

    class Config:
        from_attributes = True


class User(UserResponse):
    """Full user model including hashed password (for internal use)."""
    hashed_password: str
