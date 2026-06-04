"""
Service for API key management
"""
import uuid
from datetime import datetime
from typing import Optional
import aiosqlite

from core.config import settings
from core.security import generate_api_key, verify_api_key_hash
from core.logging_config import get_logger
from models.api_key import ApiKeyCreate, ApiKeyResponse, ApiKeyCreateResponse

logger = get_logger(__name__)


async def create_api_key(
    user_id: str,
    key_data: ApiKeyCreate
) -> ApiKeyCreateResponse:
    """
    Create a new API key for a user.

    Args:
        user_id: User ID creating the key
        key_data: API key creation data

    Returns:
        ApiKeyCreateResponse with full key (shown only once)
    """
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row

        # Generate API key
        full_key, key_hash, key_prefix = generate_api_key()

        # Create database entry
        key_id = str(uuid.uuid4())
        created_at = datetime.utcnow()

        await db.execute("""
            INSERT INTO api_keys (
                id, user_id, name, key_hash, key_prefix,
                created_at, expires_at, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            key_id, user_id, key_data.name, key_hash, key_prefix,
            created_at, key_data.expires_at, True
        ))

        await db.commit()

        logger.info(f"Created API key {key_id} for user {user_id}: {key_data.name}")

        return ApiKeyCreateResponse(
            id=key_id,
            name=key_data.name,
            api_key=full_key,
            key_prefix=key_prefix,
            created_at=created_at,
            expires_at=key_data.expires_at,
            is_active=True
        )


async def verify_api_key(api_key: str) -> Optional[str]:
    """
    Verify an API key and return the associated user ID.

    Args:
        api_key: The API key to verify

    Returns:
        User ID if key is valid and active, None otherwise
    """
    # Extract prefix for quick lookup
    key_prefix = api_key[:16]

    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row

        # Find key by prefix (much faster than checking all hashes)
        cursor = await db.execute("""
            SELECT id, user_id, key_hash, expires_at, is_active
            FROM api_keys
            WHERE key_prefix = ? AND is_active = 1
        """, (key_prefix,))

        row = await cursor.fetchone()

        if not row:
            return None

        # Verify hash
        if not verify_api_key_hash(api_key, row['key_hash']):
            return None

        # Check expiration
        if row['expires_at']:
            expires_at = datetime.fromisoformat(row['expires_at'])
            if datetime.utcnow() > expires_at:
                logger.info(f"API key {row['id']} has expired")
                return None

        # Update last_used_at
        await db.execute("""
            UPDATE api_keys
            SET last_used_at = ?
            WHERE id = ?
        """, (datetime.utcnow(), row['id']))

        await db.commit()

        return row['user_id']


async def list_api_keys(user_id: str) -> list[ApiKeyResponse]:
    """
    List all API keys for a user.

    Args:
        user_id: User ID to list keys for

    Returns:
        List of ApiKeyResponse objects (without full keys)
    """
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute("""
            SELECT id, name, key_prefix, created_at, last_used_at, expires_at, is_active
            FROM api_keys
            WHERE user_id = ?
            ORDER BY created_at DESC
        """, (user_id,))

        rows = await cursor.fetchall()

        keys = []
        for row in rows:
            keys.append(ApiKeyResponse(
                id=row['id'],
                name=row['name'],
                key_prefix=row['key_prefix'],
                created_at=datetime.fromisoformat(row['created_at']),
                last_used_at=datetime.fromisoformat(row['last_used_at']) if row['last_used_at'] else None,
                expires_at=datetime.fromisoformat(row['expires_at']) if row['expires_at'] else None,
                is_active=bool(row['is_active'])
            ))

        return keys


async def delete_api_key(user_id: str, key_id: str) -> bool:
    """
    Delete an API key (user must own the key).

    Args:
        user_id: User ID requesting deletion
        key_id: API key ID to delete

    Returns:
        True if deleted, False if not found or not owned
    """
    async with aiosqlite.connect(settings.sqlite_path) as db:
        # Verify ownership
        cursor = await db.execute("""
            SELECT user_id FROM api_keys WHERE id = ?
        """, (key_id,))

        row = await cursor.fetchone()

        if not row or row[0] != user_id:
            return False

        # Delete key
        await db.execute("DELETE FROM api_keys WHERE id = ?", (key_id,))
        await db.commit()

        logger.info(f"Deleted API key {key_id} for user {user_id}")
        return True


async def toggle_api_key(user_id: str, key_id: str, is_active: bool) -> bool:
    """
    Enable or disable an API key (user must own the key).

    Args:
        user_id: User ID requesting toggle
        key_id: API key ID to toggle
        is_active: New active status

    Returns:
        True if updated, False if not found or not owned
    """
    async with aiosqlite.connect(settings.sqlite_path) as db:
        # Verify ownership
        cursor = await db.execute("""
            SELECT user_id FROM api_keys WHERE id = ?
        """, (key_id,))

        row = await cursor.fetchone()

        if not row or row[0] != user_id:
            return False

        # Update status
        await db.execute("""
            UPDATE api_keys
            SET is_active = ?
            WHERE id = ?
        """, (is_active, key_id))

        await db.commit()

        action = "enabled" if is_active else "disabled"
        logger.info(f"{action.capitalize()} API key {key_id} for user {user_id}")
        return True
