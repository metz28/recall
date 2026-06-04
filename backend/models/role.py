"""Role and permission models for RBAC."""
from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field


class Permission(BaseModel):
    """Single permission in format {resource}:{action}"""
    resource: str  # e.g., "document", "collection", "search", "*"
    action: str  # e.g., "read", "write", "delete", "*"

    def __str__(self) -> str:
        return f"{self.resource}:{self.action}"

    @classmethod
    def from_string(cls, perm_str: str) -> "Permission":
        """Parse permission from string format 'resource:action'"""
        parts = perm_str.split(":", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid permission format: {perm_str}")
        return cls(resource=parts[0], action=parts[1])


class RoleCreate(BaseModel):
    """Request to create a custom role."""
    name: str = Field(..., min_length=1, max_length=50, description="Unique role name")
    display_name: str = Field(..., min_length=1, max_length=100, description="Human-readable name")
    description: Optional[str] = Field(None, max_length=500, description="Role description")
    permissions: list[str] = Field(..., min_items=1, description="List of permissions (resource:action)")


class RoleUpdate(BaseModel):
    """Request to update a custom role."""
    display_name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    permissions: Optional[list[str]] = Field(None, min_items=1)


class RoleResponse(BaseModel):
    """Role information."""
    id: str
    name: str
    display_name: str
    description: Optional[str]
    permissions: list[str]
    is_system: bool
    is_custom: bool
    created_by: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]


class RoleList(BaseModel):
    """List of roles."""
    roles: list[RoleResponse]
    total: int


class RoleAssignmentCreate(BaseModel):
    """Request to assign a role to a user."""
    role_id: str = Field(..., description="Role to assign")
    user_id: str = Field(..., description="User to assign role to")
    resource_type: Literal["document", "collection", "global"] = Field(..., description="Resource type")
    resource_id: Optional[str] = Field(None, description="Resource ID (NULL for global roles)")
    expires_at: Optional[datetime] = Field(None, description="Optional expiration date")


class RoleAssignmentResponse(BaseModel):
    """Role assignment information."""
    id: str
    role_id: str
    role_name: str
    role_display_name: str
    user_id: str
    user_email: str
    user_username: str
    resource_type: str
    resource_id: Optional[str]
    assigned_by: str
    assigned_at: datetime
    expires_at: Optional[datetime]


class RoleAssignmentList(BaseModel):
    """List of role assignments."""
    assignments: list[RoleAssignmentResponse]
    total: int


class PermissionCheckRequest(BaseModel):
    """Request to check if user has a specific permission."""
    user_id: str
    resource_type: str
    resource_id: Optional[str] = None
    permission: str  # Format: "resource:action"


class PermissionCheckResponse(BaseModel):
    """Response for permission check."""
    has_permission: bool
    granted_permissions: list[str]  # All permissions user has for this resource


class SystemRoles:
    """System role definitions."""
    VIEWER = "viewer"
    EDITOR = "editor"
    ANALYST = "analyst"
    ADMIN = "admin"
    OWNER = "owner"

    @staticmethod
    def get_role_permissions() -> dict[str, list[str]]:
        """Get system role permission mappings."""
        return {
            SystemRoles.VIEWER: [
                "document:read",
                "collection:read",
                "search:execute"
            ],
            SystemRoles.EDITOR: [
                "document:read",
                "document:write",
                "collection:read",
                "collection:write",
                "search:execute",
                "export:create"
            ],
            SystemRoles.ANALYST: [
                "document:read",
                "collection:read",
                "search:execute",
                "search:advanced",
                "graph:explore",
                "entity:view",
                "export:create"
            ],
            SystemRoles.ADMIN: [
                "document:read",
                "document:write",
                "document:share",
                "collection:read",
                "collection:write",
                "collection:manage",
                "search:execute",
                "search:advanced",
                "export:create",
                "collaborator:add",
                "collaborator:remove",
                "role:assign"
            ],
            SystemRoles.OWNER: [
                "*:*"  # Wildcard for complete control
            ]
        }

    @staticmethod
    def get_role_descriptions() -> dict[str, tuple[str, str]]:
        """Get system role display names and descriptions."""
        return {
            SystemRoles.VIEWER: (
                "Viewer",
                "Read-only access to documents, collections, and search"
            ),
            SystemRoles.EDITOR: (
                "Editor",
                "Can view and edit documents and collections, create exports"
            ),
            SystemRoles.ANALYST: (
                "Analyst",
                "Advanced search, graph exploration, entity analysis, and exports"
            ),
            SystemRoles.ADMIN: (
                "Administrator",
                "Full access except deletion, can manage collaborators and assign roles"
            ),
            SystemRoles.OWNER: (
                "Owner",
                "Complete control over the resource, including deletion"
            )
        }
