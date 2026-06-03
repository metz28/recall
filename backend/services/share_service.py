"""
Service for managing shareable links
"""
import secrets
import uuid
import json
from datetime import datetime, timedelta
from typing import Optional
import aiosqlite

from core.config import settings
from core.logging_config import get_logger
from models.share import ShareCreate, ShareResponse, ShareMetadata

logger = get_logger(__name__)


def generate_share_token(length: int = 32) -> str:
    """Generate a secure random token for sharing"""
    return secrets.token_urlsafe(length)


def get_share_url(token: str) -> str:
    """Generate the full URL for a shared resource"""
    frontend_url = settings.frontend_url.rstrip('/')
    return f"{frontend_url}/shared/{token}"


async def create_share(
    user_id: str,
    share_data: ShareCreate
) -> ShareResponse:
    """Create a new shareable link"""
    share_id = str(uuid.uuid4())
    token = generate_share_token()
    created_at = datetime.utcnow()
    expires_at = None

    if share_data.expires_in_days:
        expires_at = created_at + timedelta(days=share_data.expires_in_days)

    # Serialize metadata to JSON
    metadata_json = json.dumps(share_data.metadata) if share_data.metadata else None

    async with aiosqlite.connect(settings.sqlite_path) as db:
        # Verify resource ownership if resource_id is provided
        if share_data.resource_id:
            if share_data.resource_type == "document":
                cursor = await db.execute(
                    "SELECT id FROM documents WHERE id = ? AND user_id = ?",
                    (share_data.resource_id, user_id)
                )
                doc = await cursor.fetchone()
                if not doc:
                    raise ValueError("Document not found or you don't have permission to share it")
            elif share_data.resource_type == "collection":
                # Collections are implicitly user-scoped, verify documents exist
                cursor = await db.execute(
                    "SELECT COUNT(*) FROM documents WHERE collection = ? AND user_id = ?",
                    (share_data.resource_id, user_id)
                )
                count = (await cursor.fetchone())[0]
                if count == 0:
                    raise ValueError("Collection not found or is empty")

        # Insert share record
        await db.execute("""
            INSERT INTO shared_links (
                id, token, resource_type, resource_id, owner_id,
                created_at, expires_at, access_level, is_active, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            share_id, token, share_data.resource_type, share_data.resource_id,
            user_id, created_at, expires_at, share_data.access_level, True, metadata_json
        ))
        await db.commit()

    logger.info(f"Created share link {share_id} for user {user_id}")

    return ShareResponse(
        id=share_id,
        token=token,
        resource_type=share_data.resource_type,
        resource_id=share_data.resource_id,
        owner_id=user_id,
        created_at=created_at,
        expires_at=expires_at,
        access_level=share_data.access_level,
        is_active=True,
        metadata=share_data.metadata,
        view_count=0,
        last_accessed=None,
        share_url=get_share_url(token)
    )


async def get_share_by_token(token: str) -> Optional[dict]:
    """Retrieve share information by token"""
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT * FROM shared_links WHERE token = ?
        """, (token,))
        row = await cursor.fetchone()

        if not row:
            return None

        return dict(row)


async def validate_share_token(token: str) -> tuple[bool, Optional[str]]:
    """
    Validate a share token
    Returns: (is_valid, error_message)
    """
    share = await get_share_by_token(token)

    if not share:
        return False, "Share link not found"

    if not share['is_active']:
        return False, "Share link has been revoked"

    if share['expires_at']:
        expires_at = datetime.fromisoformat(share['expires_at'])
        if datetime.utcnow() > expires_at:
            return False, "Share link has expired"

    return True, None


async def increment_view_count(token: str):
    """Increment view count and update last accessed time"""
    async with aiosqlite.connect(settings.sqlite_path) as db:
        await db.execute("""
            UPDATE shared_links
            SET view_count = view_count + 1,
                last_accessed = ?
            WHERE token = ?
        """, (datetime.utcnow(), token))
        await db.commit()


async def get_user_shares(user_id: str) -> list[ShareResponse]:
    """Get all shares created by a user"""
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT * FROM shared_links
            WHERE owner_id = ?
            ORDER BY created_at DESC
        """, (user_id,))
        rows = await cursor.fetchall()

        shares = []
        for row in rows:
            metadata = json.loads(row['metadata']) if row['metadata'] else None
            shares.append(ShareResponse(
                id=row['id'],
                token=row['token'],
                resource_type=row['resource_type'],
                resource_id=row['resource_id'],
                owner_id=row['owner_id'],
                created_at=datetime.fromisoformat(row['created_at']),
                expires_at=datetime.fromisoformat(row['expires_at']) if row['expires_at'] else None,
                access_level=row['access_level'],
                is_active=bool(row['is_active']),
                metadata=metadata,
                view_count=row['view_count'],
                last_accessed=datetime.fromisoformat(row['last_accessed']) if row['last_accessed'] else None,
                share_url=get_share_url(row['token'])
            ))

        return shares


async def revoke_share(user_id: str, share_id: str) -> bool:
    """Revoke a share link (set is_active to False)"""
    async with aiosqlite.connect(settings.sqlite_path) as db:
        cursor = await db.execute("""
            UPDATE shared_links
            SET is_active = 0
            WHERE id = ? AND owner_id = ?
        """, (share_id, user_id))
        await db.commit()

        if cursor.rowcount == 0:
            return False

        logger.info(f"Revoked share link {share_id}")
        return True


async def delete_share(user_id: str, share_id: str) -> bool:
    """Permanently delete a share link"""
    async with aiosqlite.connect(settings.sqlite_path) as db:
        cursor = await db.execute("""
            DELETE FROM shared_links
            WHERE id = ? AND owner_id = ?
        """, (share_id, user_id))
        await db.commit()

        if cursor.rowcount == 0:
            return False

        logger.info(f"Deleted share link {share_id}")
        return True


async def get_share_metadata(token: str) -> Optional[ShareMetadata]:
    """Get public metadata about a share (for preview/validation)"""
    share = await get_share_by_token(token)

    if not share:
        return None

    # Get owner username
    async with aiosqlite.connect(settings.sqlite_path) as db:
        cursor = await db.execute(
            "SELECT username FROM users WHERE id = ?",
            (share['owner_id'],)
        )
        owner = await cursor.fetchone()
        owner_username = owner[0] if owner else "Unknown"

        # Get resource title if applicable
        resource_title = None
        if share['resource_type'] == 'document' and share['resource_id']:
            cursor = await db.execute(
                "SELECT title FROM documents WHERE id = ?",
                (share['resource_id'],)
            )
            doc = await cursor.fetchone()
            resource_title = doc[0] if doc else None
        elif share['resource_type'] == 'search' and share['metadata']:
            metadata = json.loads(share['metadata'])
            resource_title = f"Search: {metadata.get('query', 'N/A')}"
        elif share['resource_type'] == 'collection' and share['resource_id']:
            resource_title = f"Collection: {share['resource_id']}"

    expires_at = datetime.fromisoformat(share['expires_at']) if share['expires_at'] else None
    is_expired = False
    if expires_at:
        is_expired = datetime.utcnow() > expires_at

    return ShareMetadata(
        resource_type=share['resource_type'],
        resource_title=resource_title,
        owner_username=owner_username,
        created_at=datetime.fromisoformat(share['created_at']),
        expires_at=expires_at,
        is_active=bool(share['is_active']),
        is_expired=is_expired
    )
