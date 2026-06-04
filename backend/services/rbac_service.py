"""
Service for Role-Based Access Control (RBAC)
"""
import uuid
from datetime import datetime
from typing import Optional, Set
import aiosqlite
import json

from core.config import settings
from core.logging_config import get_logger
from models.role import (
    SystemRoles, RoleCreate, RoleUpdate, RoleResponse,
    RoleAssignmentCreate, RoleAssignmentResponse
)

logger = get_logger(__name__)


async def create_system_roles():
    """Create the 5 predefined system roles."""
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row

        role_permissions = SystemRoles.get_role_permissions()
        role_descriptions = SystemRoles.get_role_descriptions()

        for role_name, permissions in role_permissions.items():
            # Check if role already exists
            cursor = await db.execute(
                "SELECT id FROM roles WHERE name = ?",
                (role_name,)
            )
            if await cursor.fetchone():
                continue

            display_name, description = role_descriptions[role_name]
            role_id = str(uuid.uuid4())
            created_at = datetime.utcnow()

            await db.execute("""
                INSERT INTO roles (
                    id, name, display_name, description, permissions,
                    is_system, is_custom, created_by, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                role_id, role_name, display_name, description,
                json.dumps(permissions), True, False, None, created_at
            ))

            logger.info(f"Created system role: {role_name}")

        await db.commit()


async def check_permission(
    user_id: str,
    resource_type: str,
    resource_id: Optional[str],
    permission: str
) -> bool:
    """
    Check if user has a specific permission for a resource.

    Args:
        user_id: User ID to check
        resource_type: Type of resource ("document", "collection", "global")
        resource_id: Resource ID (None for global)
        permission: Permission to check (format: "resource:action")

    Returns:
        True if user has permission, False otherwise
    """
    permissions = await get_user_permissions(user_id, resource_type, resource_id)

    # Check for wildcard permission
    if "*:*" in permissions:
        return True

    # Check for exact permission
    if permission in permissions:
        return True

    # Check for resource wildcard (e.g., "document:*")
    perm_parts = permission.split(":", 1)
    if len(perm_parts) == 2:
        resource_wildcard = f"{perm_parts[0]}:*"
        if resource_wildcard in permissions:
            return True

    # Check for action wildcard (e.g., "*:read")
    action_wildcard = f"*:{perm_parts[1]}"
    if action_wildcard in permissions:
        return True

    return False


async def get_user_permissions(
    user_id: str,
    resource_type: str,
    resource_id: Optional[str]
) -> Set[str]:
    """
    Get all permissions a user has for a specific resource.

    Args:
        user_id: User ID
        resource_type: Type of resource ("document", "collection", "global")
        resource_id: Resource ID (None for global)

    Returns:
        Set of permission strings
    """
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row

        # Check if user is owner of the resource
        if resource_type == "document" and resource_id:
            cursor = await db.execute(
                "SELECT user_id FROM documents WHERE id = ?",
                (resource_id,)
            )
            doc = await cursor.fetchone()
            if doc and doc['user_id'] == user_id:
                return {"*:*"}  # Owner has all permissions

        # Get role assignments for this user and resource
        cursor = await db.execute("""
            SELECT r.permissions
            FROM role_assignments ra
            JOIN roles r ON ra.role_id = r.id
            WHERE ra.user_id = ?
              AND ra.resource_type = ?
              AND (ra.resource_id = ? OR ra.resource_id IS NULL)
              AND (ra.expires_at IS NULL OR ra.expires_at > ?)
        """, (user_id, resource_type, resource_id, datetime.utcnow()))

        rows = await cursor.fetchall()

        # Collect all permissions from all roles
        all_permissions = set()
        for row in rows:
            permissions = json.loads(row['permissions'])
            all_permissions.update(permissions)

        # Also check global role assignments
        if resource_type != "global":
            cursor = await db.execute("""
                SELECT r.permissions
                FROM role_assignments ra
                JOIN roles r ON ra.role_id = r.id
                WHERE ra.user_id = ?
                  AND ra.resource_type = 'global'
                  AND (ra.expires_at IS NULL OR ra.expires_at > ?)
            """, (user_id, datetime.utcnow()))

            rows = await cursor.fetchall()
            for row in rows:
                permissions = json.loads(row['permissions'])
                all_permissions.update(permissions)

        return all_permissions


async def assign_role(
    assigner_id: str,
    assignment_data: RoleAssignmentCreate
) -> RoleAssignmentResponse:
    """
    Assign a role to a user for a specific resource.

    Args:
        assigner_id: User ID performing the assignment
        assignment_data: Role assignment data

    Returns:
        RoleAssignmentResponse with assignment details

    Raises:
        ValueError: If role or user not found
        PermissionError: If assigner doesn't have permission
    """
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row

        # Verify assigner has permission to assign roles
        if assignment_data.resource_type != "global":
            has_permission = await check_permission(
                assigner_id,
                assignment_data.resource_type,
                assignment_data.resource_id,
                "role:assign"
            )

            if not has_permission:
                # Check if assigner is owner
                if assignment_data.resource_type == "document" and assignment_data.resource_id:
                    cursor = await db.execute(
                        "SELECT user_id FROM documents WHERE id = ?",
                        (assignment_data.resource_id,)
                    )
                    doc = await cursor.fetchone()
                    if not doc or doc['user_id'] != assigner_id:
                        raise PermissionError("You don't have permission to assign roles for this resource")
                else:
                    raise PermissionError("You don't have permission to assign roles for this resource")

        # Verify role exists
        cursor = await db.execute(
            "SELECT name, display_name FROM roles WHERE id = ?",
            (assignment_data.role_id,)
        )
        role = await cursor.fetchone()
        if not role:
            raise ValueError("Role not found")

        # Verify user exists
        cursor = await db.execute(
            "SELECT email, username FROM users WHERE id = ?",
            (assignment_data.user_id,)
        )
        user = await cursor.fetchone()
        if not user:
            raise ValueError("User not found")

        # Check if assignment already exists
        cursor = await db.execute("""
            SELECT id FROM role_assignments
            WHERE role_id = ? AND user_id = ?
              AND resource_type = ?
              AND (resource_id = ? OR (resource_id IS NULL AND ? IS NULL))
        """, (
            assignment_data.role_id, assignment_data.user_id,
            assignment_data.resource_type, assignment_data.resource_id,
            assignment_data.resource_id
        ))

        existing = await cursor.fetchone()
        if existing:
            raise ValueError("User already has this role for this resource")

        # Create assignment
        assignment_id = str(uuid.uuid4())
        assigned_at = datetime.utcnow()

        await db.execute("""
            INSERT INTO role_assignments (
                id, role_id, user_id, resource_type, resource_id,
                assigned_by, assigned_at, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            assignment_id, assignment_data.role_id, assignment_data.user_id,
            assignment_data.resource_type, assignment_data.resource_id,
            assigner_id, assigned_at, assignment_data.expires_at
        ))

        await db.commit()

        logger.info(
            f"Assigned role {role['name']} to user {assignment_data.user_id} "
            f"for {assignment_data.resource_type}"
        )

        return RoleAssignmentResponse(
            id=assignment_id,
            role_id=assignment_data.role_id,
            role_name=role['name'],
            role_display_name=role['display_name'],
            user_id=assignment_data.user_id,
            user_email=user['email'],
            user_username=user['username'],
            resource_type=assignment_data.resource_type,
            resource_id=assignment_data.resource_id,
            assigned_by=assigner_id,
            assigned_at=assigned_at,
            expires_at=assignment_data.expires_at
        )


async def revoke_role_assignment(
    revoker_id: str,
    assignment_id: str
) -> bool:
    """
    Revoke a role assignment.

    Args:
        revoker_id: User ID performing the revocation
        assignment_id: Assignment ID to revoke

    Returns:
        True if revoked, False if not found

    Raises:
        PermissionError: If revoker doesn't have permission
    """
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row

        # Get assignment details
        cursor = await db.execute("""
            SELECT resource_type, resource_id, user_id
            FROM role_assignments
            WHERE id = ?
        """, (assignment_id,))

        assignment = await cursor.fetchone()
        if not assignment:
            return False

        # Verify revoker has permission
        has_permission = await check_permission(
            revoker_id,
            assignment['resource_type'],
            assignment['resource_id'],
            "role:assign"
        )

        if not has_permission:
            # Check if revoker is owner
            if assignment['resource_type'] == "document" and assignment['resource_id']:
                cursor = await db.execute(
                    "SELECT user_id FROM documents WHERE id = ?",
                    (assignment['resource_id'],)
                )
                doc = await cursor.fetchone()
                if not doc or doc['user_id'] != revoker_id:
                    # Allow users to revoke their own assignments
                    if assignment['user_id'] != revoker_id:
                        raise PermissionError("You don't have permission to revoke this role assignment")
            else:
                # Allow users to revoke their own assignments
                if assignment['user_id'] != revoker_id:
                    raise PermissionError("You don't have permission to revoke this role assignment")

        # Delete assignment
        await db.execute("DELETE FROM role_assignments WHERE id = ?", (assignment_id,))
        await db.commit()

        logger.info(f"Revoked role assignment {assignment_id}")
        return True


async def create_custom_role(
    creator_id: str,
    role_data: RoleCreate
) -> RoleResponse:
    """
    Create a custom role.

    Args:
        creator_id: User ID creating the role
        role_data: Role creation data

    Returns:
        RoleResponse with created role details

    Raises:
        ValueError: If role name already exists
    """
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row

        # Check if role name already exists
        cursor = await db.execute(
            "SELECT id FROM roles WHERE name = ?",
            (role_data.name,)
        )
        if await cursor.fetchone():
            raise ValueError(f"Role with name '{role_data.name}' already exists")

        # Create role
        role_id = str(uuid.uuid4())
        created_at = datetime.utcnow()

        await db.execute("""
            INSERT INTO roles (
                id, name, display_name, description, permissions,
                is_system, is_custom, created_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            role_id, role_data.name, role_data.display_name,
            role_data.description, json.dumps(role_data.permissions),
            False, True, creator_id, created_at
        ))

        await db.commit()

        logger.info(f"Created custom role: {role_data.name}")

        return RoleResponse(
            id=role_id,
            name=role_data.name,
            display_name=role_data.display_name,
            description=role_data.description,
            permissions=role_data.permissions,
            is_system=False,
            is_custom=True,
            created_by=creator_id,
            created_at=created_at,
            updated_at=None
        )


async def update_custom_role(
    updater_id: str,
    role_id: str,
    role_data: RoleUpdate
) -> Optional[RoleResponse]:
    """
    Update a custom role (system roles cannot be updated).

    Args:
        updater_id: User ID updating the role
        role_id: Role ID to update
        role_data: Updated role data

    Returns:
        RoleResponse if updated, None if not found

    Raises:
        PermissionError: If trying to update system role or not creator
    """
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row

        # Get role
        cursor = await db.execute(
            "SELECT * FROM roles WHERE id = ?",
            (role_id,)
        )
        role = await cursor.fetchone()

        if not role:
            return None

        if role['is_system']:
            raise PermissionError("Cannot update system roles")

        if role['created_by'] != updater_id:
            raise PermissionError("You can only update roles you created")

        # Build update query
        updates = []
        params = []

        if role_data.display_name is not None:
            updates.append("display_name = ?")
            params.append(role_data.display_name)

        if role_data.description is not None:
            updates.append("description = ?")
            params.append(role_data.description)

        if role_data.permissions is not None:
            updates.append("permissions = ?")
            params.append(json.dumps(role_data.permissions))

        if not updates:
            # No changes
            return None

        updates.append("updated_at = ?")
        updated_at = datetime.utcnow()
        params.append(updated_at)
        params.append(role_id)

        await db.execute(
            f"UPDATE roles SET {', '.join(updates)} WHERE id = ?",
            params
        )

        await db.commit()

        # Fetch updated role
        cursor = await db.execute("SELECT * FROM roles WHERE id = ?", (role_id,))
        updated_role = await cursor.fetchone()

        logger.info(f"Updated custom role: {role['name']}")

        return RoleResponse(
            id=updated_role['id'],
            name=updated_role['name'],
            display_name=updated_role['display_name'],
            description=updated_role['description'],
            permissions=json.loads(updated_role['permissions']),
            is_system=bool(updated_role['is_system']),
            is_custom=bool(updated_role['is_custom']),
            created_by=updated_role['created_by'],
            created_at=datetime.fromisoformat(updated_role['created_at']),
            updated_at=datetime.fromisoformat(updated_role['updated_at']) if updated_role['updated_at'] else None
        )


async def delete_custom_role(
    deleter_id: str,
    role_id: str
) -> bool:
    """
    Delete a custom role (system roles cannot be deleted).

    Args:
        deleter_id: User ID deleting the role
        role_id: Role ID to delete

    Returns:
        True if deleted, False if not found

    Raises:
        PermissionError: If trying to delete system role or not creator
    """
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row

        # Get role
        cursor = await db.execute(
            "SELECT is_system, created_by FROM roles WHERE id = ?",
            (role_id,)
        )
        role = await cursor.fetchone()

        if not role:
            return False

        if role['is_system']:
            raise PermissionError("Cannot delete system roles")

        if role['created_by'] != deleter_id:
            raise PermissionError("You can only delete roles you created")

        # Delete role (cascade will delete assignments)
        await db.execute("DELETE FROM roles WHERE id = ?", (role_id,))
        await db.commit()

        logger.info(f"Deleted custom role {role_id}")
        return True


async def list_roles() -> list[RoleResponse]:
    """List all roles (system and custom)."""
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("""
            SELECT * FROM roles
            ORDER BY is_system DESC, name ASC
        """)

        rows = await cursor.fetchall()

        roles = []
        for row in rows:
            roles.append(RoleResponse(
                id=row['id'],
                name=row['name'],
                display_name=row['display_name'],
                description=row['description'],
                permissions=json.loads(row['permissions']),
                is_system=bool(row['is_system']),
                is_custom=bool(row['is_custom']),
                created_by=row['created_by'],
                created_at=datetime.fromisoformat(row['created_at']),
                updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
            ))

        return roles


async def get_role(role_id: str) -> Optional[RoleResponse]:
    """Get a specific role by ID."""
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("SELECT * FROM roles WHERE id = ?", (role_id,))
        row = await cursor.fetchone()

        if not row:
            return None

        return RoleResponse(
            id=row['id'],
            name=row['name'],
            display_name=row['display_name'],
            description=row['description'],
            permissions=json.loads(row['permissions']),
            is_system=bool(row['is_system']),
            is_custom=bool(row['is_custom']),
            created_by=row['created_by'],
            created_at=datetime.fromisoformat(row['created_at']),
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
        )


async def get_user_role_assignments(user_id: str) -> list[RoleAssignmentResponse]:
    """Get all role assignments for a user."""
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("""
            SELECT ra.*, r.name as role_name, r.display_name as role_display_name,
                   u.email, u.username
            FROM role_assignments ra
            JOIN roles r ON ra.role_id = r.id
            JOIN users u ON ra.user_id = u.id
            WHERE ra.user_id = ?
            ORDER BY ra.assigned_at DESC
        """, (user_id,))

        rows = await cursor.fetchall()

        assignments = []
        for row in rows:
            assignments.append(RoleAssignmentResponse(
                id=row['id'],
                role_id=row['role_id'],
                role_name=row['role_name'],
                role_display_name=row['role_display_name'],
                user_id=row['user_id'],
                user_email=row['email'],
                user_username=row['username'],
                resource_type=row['resource_type'],
                resource_id=row['resource_id'],
                assigned_by=row['assigned_by'],
                assigned_at=datetime.fromisoformat(row['assigned_at']),
                expires_at=datetime.fromisoformat(row['expires_at']) if row['expires_at'] else None
            ))

        return assignments


async def get_resource_role_assignments(
    resource_type: str,
    resource_id: Optional[str]
) -> list[RoleAssignmentResponse]:
    """Get all role assignments for a specific resource."""
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("""
            SELECT ra.*, r.name as role_name, r.display_name as role_display_name,
                   u.email, u.username
            FROM role_assignments ra
            JOIN roles r ON ra.role_id = r.id
            JOIN users u ON ra.user_id = u.id
            WHERE ra.resource_type = ?
              AND (ra.resource_id = ? OR (ra.resource_id IS NULL AND ? IS NULL))
            ORDER BY ra.assigned_at DESC
        """, (resource_type, resource_id, resource_id))

        rows = await cursor.fetchall()

        assignments = []
        for row in rows:
            assignments.append(RoleAssignmentResponse(
                id=row['id'],
                role_id=row['role_id'],
                role_name=row['role_name'],
                role_display_name=row['role_display_name'],
                user_id=row['user_id'],
                user_email=row['email'],
                user_username=row['username'],
                resource_type=row['resource_type'],
                resource_id=row['resource_id'],
                assigned_by=row['assigned_by'],
                assigned_at=datetime.fromisoformat(row['assigned_at']),
                expires_at=datetime.fromisoformat(row['expires_at']) if row['expires_at'] else None
            ))

        return assignments
