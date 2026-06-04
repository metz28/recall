"""API Key management endpoints."""
from fastapi import APIRouter, HTTPException, Depends, status

from core.dependencies import get_current_user
from core.logging_config import get_logger
from models.user import User
from models.api_key import (
    ApiKeyCreate, ApiKeyResponse, ApiKeyCreateResponse,
    ApiKeyList, ApiKeyToggle
)
from services.api_key_service import (
    create_api_key, list_api_keys, delete_api_key, toggle_api_key
)

router = APIRouter()
logger = get_logger(__name__)


@router.post("/api-keys", response_model=ApiKeyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_new_api_key(
    key_data: ApiKeyCreate,
    current_user: User = Depends(get_current_user)
):
    """
    Create a new API key for programmatic access.

    The full API key is returned only once - save it securely.
    API keys grant full access to your account.

    Args:
        key_data: API key creation data (name, optional expiration)
        current_user: Current authenticated user (JWT only)

    Returns:
        ApiKeyCreateResponse with full API key (shown once)
    """
    try:
        api_key_response = await create_api_key(current_user.id, key_data)
        logger.info(f"User {current_user.username} created API key: {key_data.name}")
        return api_key_response
    except Exception as e:
        logger.error(f"Error creating API key: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create API key"
        )


@router.get("/api-keys", response_model=ApiKeyList)
async def list_user_api_keys(
    current_user: User = Depends(get_current_user)
):
    """
    List all API keys for the current user.

    Only shows key prefix, not full keys.

    Args:
        current_user: Current authenticated user (JWT only)

    Returns:
        ApiKeyList with all user's API keys
    """
    try:
        keys = await list_api_keys(current_user.id)
        return ApiKeyList(api_keys=keys, total=len(keys))
    except Exception as e:
        logger.error(f"Error listing API keys: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list API keys"
        )


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Revoke (delete) an API key.

    User must own the key being deleted.

    Args:
        key_id: ID of the API key to delete
        current_user: Current authenticated user (JWT only)

    Raises:
        HTTPException: 404 if key not found or not owned by user
    """
    success = await delete_api_key(current_user.id, key_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found or you don't have permission to delete it"
        )

    logger.info(f"User {current_user.username} revoked API key {key_id}")


@router.put("/api-keys/{key_id}/toggle", response_model=ApiKeyResponse)
async def toggle_api_key_status(
    key_id: str,
    toggle_data: ApiKeyToggle,
    current_user: User = Depends(get_current_user)
):
    """
    Enable or disable an API key without deleting it.

    User must own the key being toggled.

    Args:
        key_id: ID of the API key to toggle
        toggle_data: New active status
        current_user: Current authenticated user (JWT only)

    Returns:
        Updated API key information

    Raises:
        HTTPException: 404 if key not found or not owned by user
    """
    success = await toggle_api_key(current_user.id, key_id, toggle_data.is_active)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found or you don't have permission to modify it"
        )

    # Return updated key info
    keys = await list_api_keys(current_user.id)
    updated_key = next((k for k in keys if k.id == key_id), None)

    if not updated_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="API key not found after update"
        )

    action = "enabled" if toggle_data.is_active else "disabled"
    logger.info(f"User {current_user.username} {action} API key {key_id}")

    return updated_key
