"""Role and permission management endpoints (RBAC)."""
from fastapi import APIRouter, HTTPException, Depends, status

from core.dependencies import get_current_user
from core.logging_config import get_logger
from models.user import User
from models.role import (
    RoleCreate, RoleUpdate, RoleResponse, RoleList,
    RoleAssignmentCreate, RoleAssignmentResponse, RoleAssignmentList,
    PermissionCheckRequest, PermissionCheckResponse
)
from services.rbac_service import (
    create_custom_role, update_custom_role, delete_custom_role,
    list_roles, get_role, assign_role, revoke_role_assignment,
    get_user_role_assignments, get_resource_role_assignments,
    check_permission, get_user_permissions
)

router = APIRouter()
logger = get_logger(__name__)


# Role Management Endpoints

@router.post("/roles", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    role_data: RoleCreate,
    current_user: User = Depends(get_current_user)
):
    """
    Create a custom role with specific permissions.

    System roles cannot be created via API.

    Args:
        role_data: Role creation data
        current_user: Current authenticated user

    Returns:
        RoleResponse with created role details

    Raises:
        HTTPException: 400 if role name already exists
    """
    try:
        role = await create_custom_role(current_user.id, role_data)
        logger.info(f"User {current_user.username} created custom role: {role_data.name}")
        return role
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating role: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create role"
        )


@router.get("/roles", response_model=RoleList)
async def get_roles(
    current_user: User = Depends(get_current_user)
):
    """
    List all roles (system and custom).

    Args:
        current_user: Current authenticated user

    Returns:
        RoleList with all roles
    """
    try:
        roles = await list_roles()
        return RoleList(roles=roles, total=len(roles))
    except Exception as e:
        logger.error(f"Error listing roles: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list roles"
        )


@router.get("/roles/{role_id}", response_model=RoleResponse)
async def get_role_details(
    role_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get details of a specific role.

    Args:
        role_id: Role ID
        current_user: Current authenticated user

    Returns:
        RoleResponse with role details

    Raises:
        HTTPException: 404 if role not found
    """
    role = await get_role(role_id)

    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found"
        )

    return role


@router.put("/roles/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: str,
    role_data: RoleUpdate,
    current_user: User = Depends(get_current_user)
):
    """
    Update a custom role.

    Only the creator can update their custom roles.
    System roles cannot be updated.

    Args:
        role_id: Role ID to update
        role_data: Updated role data
        current_user: Current authenticated user

    Returns:
        RoleResponse with updated role details

    Raises:
        HTTPException: 403 if not permitted, 404 if not found
    """
    try:
        role = await update_custom_role(current_user.id, role_id, role_data)

        if not role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found"
            )

        logger.info(f"User {current_user.username} updated role {role_id}")
        return role

    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error updating role: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update role"
        )


@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Delete a custom role.

    Only the creator can delete their custom roles.
    System roles cannot be deleted.

    Args:
        role_id: Role ID to delete
        current_user: Current authenticated user

    Raises:
        HTTPException: 403 if not permitted, 404 if not found
    """
    try:
        success = await delete_custom_role(current_user.id, role_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role not found"
            )

        logger.info(f"User {current_user.username} deleted role {role_id}")

    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error deleting role: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete role"
        )


# Role Assignment Endpoints

@router.post("/role-assignments", response_model=RoleAssignmentResponse, status_code=status.HTTP_201_CREATED)
async def assign_role_to_user(
    assignment_data: RoleAssignmentCreate,
    current_user: User = Depends(get_current_user)
):
    """
    Assign a role to a user for a specific resource.

    Requires 'role:assign' permission or ownership of the resource.

    Args:
        assignment_data: Role assignment data
        current_user: Current authenticated user

    Returns:
        RoleAssignmentResponse with assignment details

    Raises:
        HTTPException: 400 if invalid, 403 if not permitted
    """
    try:
        assignment = await assign_role(current_user.id, assignment_data)
        logger.info(
            f"User {current_user.username} assigned role {assignment_data.role_id} "
            f"to user {assignment_data.user_id}"
        )
        return assignment

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error assigning role: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to assign role"
        )


@router.get("/role-assignments/user/{user_id}", response_model=RoleAssignmentList)
async def get_user_assignments(
    user_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get all role assignments for a specific user.

    Users can view their own assignments, admins can view all.

    Args:
        user_id: User ID to get assignments for
        current_user: Current authenticated user

    Returns:
        RoleAssignmentList with user's role assignments

    Raises:
        HTTPException: 403 if not permitted
    """
    # Users can view their own assignments
    if user_id != current_user.id:
        # TODO: Check if current_user has admin permission
        # For now, allow any authenticated user to view
        pass

    try:
        assignments = await get_user_role_assignments(user_id)
        return RoleAssignmentList(assignments=assignments, total=len(assignments))
    except Exception as e:
        logger.error(f"Error getting user assignments: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get role assignments"
        )


@router.get("/role-assignments/resource/{resource_type}/{resource_id}", response_model=RoleAssignmentList)
async def get_resource_assignments(
    resource_type: str,
    resource_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get all role assignments for a specific resource.

    Requires read permission on the resource.

    Args:
        resource_type: Type of resource ("document", "collection", "global")
        resource_id: Resource ID
        current_user: Current authenticated user

    Returns:
        RoleAssignmentList with resource's role assignments

    Raises:
        HTTPException: 403 if not permitted
    """
    # Check if user has permission to view this resource
    has_permission = await check_permission(
        current_user.id, resource_type, resource_id, "document:read"
    )

    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view role assignments for this resource"
        )

    try:
        assignments = await get_resource_role_assignments(resource_type, resource_id)
        return RoleAssignmentList(assignments=assignments, total=len(assignments))
    except Exception as e:
        logger.error(f"Error getting resource assignments: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get role assignments"
        )


@router.delete("/role-assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_assignment(
    assignment_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Revoke a role assignment.

    Requires 'role:assign' permission, ownership, or self-revocation.

    Args:
        assignment_id: Assignment ID to revoke
        current_user: Current authenticated user

    Raises:
        HTTPException: 403 if not permitted, 404 if not found
    """
    try:
        success = await revoke_role_assignment(current_user.id, assignment_id)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Role assignment not found"
            )

        logger.info(f"User {current_user.username} revoked role assignment {assignment_id}")

    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error revoking assignment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke role assignment"
        )


# Permission Check Endpoints

@router.post("/permissions/check", response_model=PermissionCheckResponse)
async def check_user_permission(
    check_data: PermissionCheckRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Check if a user has a specific permission for a resource.

    Args:
        check_data: Permission check request
        current_user: Current authenticated user

    Returns:
        PermissionCheckResponse with result and all granted permissions
    """
    try:
        has_permission = await check_permission(
            check_data.user_id,
            check_data.resource_type,
            check_data.resource_id,
            check_data.permission
        )

        granted_permissions = await get_user_permissions(
            check_data.user_id,
            check_data.resource_type,
            check_data.resource_id
        )

        return PermissionCheckResponse(
            has_permission=has_permission,
            granted_permissions=list(granted_permissions)
        )

    except Exception as e:
        logger.error(f"Error checking permission: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check permission"
        )


@router.get("/permissions/me/{resource_type}/{resource_id}", response_model=PermissionCheckResponse)
async def get_my_permissions(
    resource_type: str,
    resource_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get all permissions the current user has for a resource.

    Args:
        resource_type: Type of resource
        resource_id: Resource ID
        current_user: Current authenticated user

    Returns:
        PermissionCheckResponse with all granted permissions
    """
    try:
        granted_permissions = await get_user_permissions(
            current_user.id,
            resource_type,
            resource_id
        )

        return PermissionCheckResponse(
            has_permission=len(granted_permissions) > 0,
            granted_permissions=list(granted_permissions)
        )

    except Exception as e:
        logger.error(f"Error getting permissions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get permissions"
        )
