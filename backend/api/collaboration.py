"""
API endpoints for multi-user collaboration
"""
from fastapi import APIRouter, Depends, HTTPException, status

from models.collaboration import (
    CollaboratorAdd, CollaboratorUpdate, CollaboratorResponse,
    CollaboratorList, SharedWithMeList, ActivityLogResponse,
    CollaborationStats
)
from models.user import User
from core.dependencies import get_current_user
from services import collaboration_service

router = APIRouter()


@router.post("/collaborators", response_model=CollaboratorResponse, status_code=status.HTTP_201_CREATED)
async def add_collaborator(
    collab_data: CollaboratorAdd,
    current_user: User = Depends(get_current_user)
):
    """
    Add a collaborator to a document or collection.

    Requires admin permission on the resource.
    """
    try:
        collaborator = await collaboration_service.add_collaborator(
            user_id=current_user.id,
            collab_data=collab_data
        )
        return collaborator
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add collaborator: {str(e)}"
        )


@router.get("/collaborators/{resource_type}/{resource_id}", response_model=CollaboratorList)
async def list_collaborators(
    resource_type: str,
    resource_id: str,
    current_user: User = Depends(get_current_user)
):
    """List all collaborators for a resource"""
    try:
        collaborators = await collaboration_service.get_collaborators(
            user_id=current_user.id,
            resource_type=resource_type,
            resource_id=resource_id
        )
        return CollaboratorList(collaborators=collaborators)
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list collaborators: {str(e)}"
        )


@router.put("/collaborators/{collaborator_id}")
async def update_collaborator(
    collaborator_id: str,
    update_data: CollaboratorUpdate,
    current_user: User = Depends(get_current_user)
):
    """Update a collaborator's permission level"""
    try:
        success = await collaboration_service.update_collaborator_permission(
            user_id=current_user.id,
            collaborator_id=collaborator_id,
            new_permission=update_data.permission
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Collaborator not found"
            )

        return {"message": "Collaborator permission updated successfully"}
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update collaborator: {str(e)}"
        )


@router.delete("/collaborators/{collaborator_id}")
async def remove_collaborator(
    collaborator_id: str,
    current_user: User = Depends(get_current_user)
):
    """Remove a collaborator from a resource"""
    try:
        success = await collaboration_service.remove_collaborator(
            user_id=current_user.id,
            collaborator_id=collaborator_id
        )

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Collaborator not found"
            )

        return {"message": "Collaborator removed successfully"}
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove collaborator: {str(e)}"
        )


@router.get("/shared-with-me", response_model=SharedWithMeList)
async def get_shared_with_me(current_user: User = Depends(get_current_user)):
    """Get all resources shared with the current user"""
    try:
        shared_items = await collaboration_service.get_shared_with_me(current_user.id)
        return SharedWithMeList(shared_items=shared_items)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get shared items: {str(e)}"
        )


@router.get("/activity/{resource_type}/{resource_id}", response_model=ActivityLogResponse)
async def get_activity_log(
    resource_type: str,
    resource_id: str,
    limit: int = 50,
    current_user: User = Depends(get_current_user)
):
    """Get activity log for a resource"""
    try:
        activities = await collaboration_service.get_activity_log(
            user_id=current_user.id,
            resource_type=resource_type,
            resource_id=resource_id,
            limit=limit
        )
        return ActivityLogResponse(
            activities=activities,
            total=len(activities)
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get activity log: {str(e)}"
        )


@router.get("/stats", response_model=CollaborationStats)
async def get_collaboration_stats(current_user: User = Depends(get_current_user)):
    """Get collaboration statistics for the current user"""
    import aiosqlite
    from core.config import settings

    try:
        async with aiosqlite.connect(settings.sqlite_path) as db:
            # Count shared by me (documents I own that have collaborators)
            cursor = await db.execute("""
                SELECT COUNT(DISTINCT c.resource_id)
                FROM collaborators c
                JOIN documents d ON c.resource_type = 'document' AND c.resource_id = d.id
                WHERE d.user_id = ?
            """, (current_user.id,))
            shared_by_me = (await cursor.fetchone())[0]

            # Count shared with me
            cursor = await db.execute("""
                SELECT COUNT(*) FROM collaborators WHERE collaborator_id = ?
            """, (current_user.id,))
            shared_with_me = (await cursor.fetchone())[0]

            # Count total collaborators on my resources
            cursor = await db.execute("""
                SELECT COUNT(*)
                FROM collaborators c
                JOIN documents d ON c.resource_type = 'document' AND c.resource_id = d.id
                WHERE d.user_id = ?
            """, (current_user.id,))
            total_collaborators = (await cursor.fetchone())[0]

            # Count recent activity (last 7 days)
            cursor = await db.execute("""
                SELECT COUNT(*)
                FROM activity_log a
                WHERE a.created_at >= datetime('now', '-7 days')
                  AND (
                    a.user_id = ?
                    OR a.resource_id IN (
                      SELECT resource_id FROM collaborators WHERE collaborator_id = ?
                    )
                  )
            """, (current_user.id, current_user.id))
            recent_activity = (await cursor.fetchone())[0]

            return CollaborationStats(
                total_shared_by_me=shared_by_me,
                total_shared_with_me=shared_with_me,
                total_collaborators=total_collaborators,
                recent_activity_count=recent_activity
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get stats: {str(e)}"
        )


@router.get("/permissions/{resource_type}/{resource_id}")
async def check_my_permission(
    resource_type: str,
    resource_id: str,
    current_user: User = Depends(get_current_user)
):
    """Check current user's permission level for a resource"""
    try:
        has_permission, permission_level = await collaboration_service.check_permission(
            user_id=current_user.id,
            resource_type=resource_type,
            resource_id=resource_id,
            required_permission="read"
        )

        return {
            "has_access": has_permission,
            "permission_level": permission_level,
            "can_read": has_permission,
            "can_write": permission_level in ["write", "admin", "owner"] if permission_level else False,
            "can_admin": permission_level in ["admin", "owner"] if permission_level else False,
            "is_owner": permission_level == "owner" if permission_level else False
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check permission: {str(e)}"
        )
