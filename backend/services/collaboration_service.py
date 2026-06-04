"""
Service for multi-user collaboration
"""
import uuid
from datetime import datetime
from typing import Optional
import aiosqlite

from core.config import settings
from core.logging_config import get_logger
from models.collaboration import (
    CollaboratorAdd, CollaboratorResponse, SharedWithMeResponse,
    ActivityLogEntry, PermissionLevel
)

logger = get_logger(__name__)


async def check_permission(
    user_id: str,
    resource_type: str,
    resource_id: str,
    required_permission: str = "read"
) -> tuple[bool, Optional[str]]:
    """
    Check if user has required permission for a resource.

    Returns: (has_permission, actual_permission)
    """
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row

        # Check if user is owner
        if resource_type == "document":
            cursor = await db.execute(
                "SELECT user_id FROM documents WHERE id = ?",
                (resource_id,)
            )
            doc = await cursor.fetchone()
            if doc and doc['user_id'] == user_id:
                return True, PermissionLevel.OWNER

        # Check collaborator permissions
        cursor = await db.execute("""
            SELECT permission FROM collaborators
            WHERE resource_type = ? AND resource_id = ? AND collaborator_id = ?
        """, (resource_type, resource_id, user_id))

        collab = await cursor.fetchone()
        if not collab:
            return False, None

        permission = collab['permission']

        # Permission hierarchy: owner > admin > write > read
        permission_levels = {
            PermissionLevel.READ: 1,
            PermissionLevel.WRITE: 2,
            PermissionLevel.ADMIN: 3,
            PermissionLevel.OWNER: 4
        }

        has_permission = permission_levels.get(permission, 0) >= permission_levels.get(required_permission, 0)
        return has_permission, permission


async def add_collaborator(
    user_id: str,
    collab_data: CollaboratorAdd
) -> CollaboratorResponse:
    """Add a collaborator to a resource (also creates RBAC role assignment)"""
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row

        # Verify user has admin permission or is owner
        has_permission, _ = await check_permission(
            user_id, collab_data.resource_type, collab_data.resource_id, "admin"
        )

        if not has_permission:
            raise PermissionError("You don't have permission to add collaborators to this resource")

        # Get collaborator by email
        cursor = await db.execute(
            "SELECT id, email, username FROM users WHERE email = ?",
            (collab_data.collaborator_email,)
        )
        collaborator = await cursor.fetchone()

        if not collaborator:
            raise ValueError(f"User with email {collab_data.collaborator_email} not found")

        collaborator_id = collaborator['id']

        # Check if already a collaborator
        cursor = await db.execute("""
            SELECT id FROM collaborators
            WHERE resource_type = ? AND resource_id = ? AND collaborator_id = ?
        """, (collab_data.resource_type, collab_data.resource_id, collaborator_id))

        existing = await cursor.fetchone()
        if existing:
            raise ValueError("User is already a collaborator on this resource")

        # Check if user is the owner (can't add owner as collaborator)
        if collab_data.resource_type == "document":
            cursor = await db.execute(
                "SELECT user_id FROM documents WHERE id = ?",
                (collab_data.resource_id,)
            )
            doc = await cursor.fetchone()
            if doc and doc['user_id'] == collaborator_id:
                raise ValueError("Cannot add the owner as a collaborator")

        # Get resource title
        resource_title = None
        if collab_data.resource_type == "document":
            cursor = await db.execute(
                "SELECT title FROM documents WHERE id = ?",
                (collab_data.resource_id,)
            )
            doc = await cursor.fetchone()
            resource_title = doc['title'] if doc else None
        elif collab_data.resource_type == "collection":
            resource_title = collab_data.resource_id

        # Add collaborator
        collab_id = str(uuid.uuid4())
        created_at = datetime.utcnow()

        await db.execute("""
            INSERT INTO collaborators (
                id, resource_type, resource_id, collaborator_id,
                permission, added_by, added_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            collab_id, collab_data.resource_type, collab_data.resource_id,
            collaborator_id, collab_data.permission, user_id, created_at
        ))

        # Also create RBAC role assignment (backward compatibility + new system)
        await _create_role_assignment_for_collaborator(
            db, collab_data.resource_type, collab_data.resource_id,
            collaborator_id, collab_data.permission, user_id, created_at
        )

        # Log activity
        await log_activity(
            db, collab_data.resource_type, collab_data.resource_id,
            user_id, "shared",
            f"Shared with {collaborator['username']} ({collab_data.permission} access)"
        )

        await db.commit()

        logger.info(f"Added collaborator {collaborator_id} to {collab_data.resource_type} {collab_data.resource_id}")

        return CollaboratorResponse(
            id=collab_id,
            resource_type=collab_data.resource_type,
            resource_id=collab_data.resource_id,
            resource_title=resource_title,
            collaborator_id=collaborator_id,
            collaborator_email=collaborator['email'],
            collaborator_username=collaborator['username'],
            permission=collab_data.permission,
            added_by=user_id,
            added_at=created_at,
            last_accessed=None
        )


async def get_collaborators(
    user_id: str,
    resource_type: str,
    resource_id: str
) -> list[CollaboratorResponse]:
    """Get all collaborators for a resource"""
    # Check permission
    has_permission, _ = await check_permission(user_id, resource_type, resource_id, "read")
    if not has_permission:
        raise PermissionError("You don't have permission to view collaborators for this resource")

    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row

        # Get resource title
        resource_title = None
        if resource_type == "document":
            cursor = await db.execute(
                "SELECT title FROM documents WHERE id = ?",
                (resource_id,)
            )
            doc = await cursor.fetchone()
            resource_title = doc['title'] if doc else None
        elif resource_type == "collection":
            resource_title = resource_id

        cursor = await db.execute("""
            SELECT c.*, u.email, u.username
            FROM collaborators c
            JOIN users u ON c.collaborator_id = u.id
            WHERE c.resource_type = ? AND c.resource_id = ?
            ORDER BY c.added_at DESC
        """, (resource_type, resource_id))

        rows = await cursor.fetchall()

        collaborators = []
        for row in rows:
            collaborators.append(CollaboratorResponse(
                id=row['id'],
                resource_type=row['resource_type'],
                resource_id=row['resource_id'],
                resource_title=resource_title,
                collaborator_id=row['collaborator_id'],
                collaborator_email=row['email'],
                collaborator_username=row['username'],
                permission=row['permission'],
                added_by=row['added_by'],
                added_at=datetime.fromisoformat(row['added_at']),
                last_accessed=datetime.fromisoformat(row['last_accessed']) if row['last_accessed'] else None
            ))

        return collaborators


async def update_collaborator_permission(
    user_id: str,
    collaborator_id: str,
    new_permission: str
) -> bool:
    """Update a collaborator's permission level"""
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row

        # Get collaborator info
        cursor = await db.execute(
            "SELECT resource_type, resource_id, collaborator_id FROM collaborators WHERE id = ?",
            (collaborator_id,)
        )
        collab = await cursor.fetchone()

        if not collab:
            return False

        # Check permission
        has_permission, _ = await check_permission(
            user_id, collab['resource_type'], collab['resource_id'], "admin"
        )

        if not has_permission:
            raise PermissionError("You don't have permission to update collaborator permissions")

        # Update permission
        await db.execute("""
            UPDATE collaborators
            SET permission = ?
            WHERE id = ?
        """, (new_permission, collaborator_id))

        # Log activity
        await log_activity(
            db, collab['resource_type'], collab['resource_id'],
            user_id, "updated_permission",
            f"Changed permission to {new_permission}"
        )

        await db.commit()

        logger.info(f"Updated collaborator {collaborator_id} permission to {new_permission}")
        return True


async def remove_collaborator(user_id: str, collaborator_id: str) -> bool:
    """Remove a collaborator from a resource"""
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row

        # Get collaborator info
        cursor = await db.execute(
            "SELECT resource_type, resource_id, collaborator_id FROM collaborators WHERE id = ?",
            (collaborator_id,)
        )
        collab = await cursor.fetchone()

        if not collab:
            return False

        # Check permission (admin can remove others, users can remove themselves)
        has_permission, _ = await check_permission(
            user_id, collab['resource_type'], collab['resource_id'], "admin"
        )

        is_self_removal = collab['collaborator_id'] == user_id

        if not has_permission and not is_self_removal:
            raise PermissionError("You don't have permission to remove this collaborator")

        # Remove collaborator
        await db.execute("DELETE FROM collaborators WHERE id = ?", (collaborator_id,))

        # Log activity
        action = "left" if is_self_removal else "removed_collaborator"
        await log_activity(
            db, collab['resource_type'], collab['resource_id'],
            user_id, action, None
        )

        await db.commit()

        logger.info(f"Removed collaborator {collaborator_id}")
        return True


async def get_shared_with_me(user_id: str) -> list[SharedWithMeResponse]:
    """Get all resources shared with the current user"""
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("""
            SELECT c.*, u.email as owner_email, u.username as owner_username,
                   d.title as doc_title
            FROM collaborators c
            LEFT JOIN documents d ON c.resource_type = 'document' AND c.resource_id = d.id
            LEFT JOIN users u ON d.user_id = u.id
            WHERE c.collaborator_id = ?
            ORDER BY c.added_at DESC
        """, (user_id,))

        rows = await cursor.fetchall()

        shared_items = []
        for row in rows:
            # Get resource title
            if row['resource_type'] == 'document':
                resource_title = row['doc_title'] or "Untitled Document"
            else:
                resource_title = row['resource_id']

            shared_items.append(SharedWithMeResponse(
                id=row['id'],
                resource_type=row['resource_type'],
                resource_id=row['resource_id'],
                resource_title=resource_title,
                owner_email=row['owner_email'] or "Unknown",
                owner_username=row['owner_username'] or "Unknown",
                permission=row['permission'],
                added_at=datetime.fromisoformat(row['added_at']),
                last_accessed=datetime.fromisoformat(row['last_accessed']) if row['last_accessed'] else None
            ))

        return shared_items


async def log_activity(
    db: aiosqlite.Connection,
    resource_type: str,
    resource_id: str,
    user_id: str,
    action: str,
    details: Optional[str] = None
):
    """Log an activity for a resource"""
    activity_id = str(uuid.uuid4())
    created_at = datetime.utcnow()

    await db.execute("""
        INSERT INTO activity_log (
            id, resource_type, resource_id, user_id, action, details, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (activity_id, resource_type, resource_id, user_id, action, details, created_at))


async def get_activity_log(
    user_id: str,
    resource_type: str,
    resource_id: str,
    limit: int = 50
) -> list[ActivityLogEntry]:
    """Get activity log for a resource"""
    # Check permission
    has_permission, _ = await check_permission(user_id, resource_type, resource_id, "read")
    if not has_permission:
        raise PermissionError("You don't have permission to view activity for this resource")

    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("""
            SELECT a.*, u.username
            FROM activity_log a
            JOIN users u ON a.user_id = u.id
            WHERE a.resource_type = ? AND a.resource_id = ?
            ORDER BY a.created_at DESC
            LIMIT ?
        """, (resource_type, resource_id, limit))

        rows = await cursor.fetchall()

        activities = []
        for row in rows:
            activities.append(ActivityLogEntry(
                id=row['id'],
                resource_type=row['resource_type'],
                resource_id=row['resource_id'],
                user_id=row['user_id'],
                username=row['username'],
                action=row['action'],
                details=row['details'],
                created_at=datetime.fromisoformat(row['created_at'])
            ))

        return activities


async def _create_role_assignment_for_collaborator(
    db: aiosqlite.Connection,
    resource_type: str,
    resource_id: str,
    collaborator_id: str,
    permission: str,
    added_by: str,
    added_at: datetime
):
    """
    Create a role assignment when adding a collaborator.
    Maps old permissions to new RBAC roles.
    """
    # Map old permission to role name
    permission_to_role = {
        "read": "viewer",
        "write": "editor",
        "admin": "admin"
    }

    role_name = permission_to_role.get(permission)
    if not role_name:
        logger.warning(f"Unknown permission type: {permission}, skipping role assignment")
        return

    # Get role ID
    cursor = await db.execute("SELECT id FROM roles WHERE name = ?", (role_name,))
    role = await cursor.fetchone()

    if not role:
        logger.warning(f"Role {role_name} not found, skipping role assignment")
        return

    role_id = role[0]

    # Check if assignment already exists
    cursor = await db.execute("""
        SELECT id FROM role_assignments
        WHERE role_id = ? AND user_id = ? AND resource_type = ? AND resource_id = ?
    """, (role_id, collaborator_id, resource_type, resource_id))

    if await cursor.fetchone():
        return  # Assignment already exists

    # Create role assignment
    assignment_id = str(uuid.uuid4())
    await db.execute("""
        INSERT INTO role_assignments (
            id, role_id, user_id, resource_type, resource_id,
            assigned_by, assigned_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (assignment_id, role_id, collaborator_id, resource_type, resource_id, added_by, added_at))

    logger.info(f"Created role assignment {role_name} for collaborator {collaborator_id}")
