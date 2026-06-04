"""Security utilities for authentication."""
from datetime import datetime, timedelta
from typing import Optional
import secrets
import hashlib

import jwt
from passlib.context import CryptContext

from core.config import settings

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: str, email: str) -> str:
    """
    Create a JWT access token.

    Args:
        user_id: User ID to encode in token
        email: User email to encode in token

    Returns:
        Encoded JWT token string
    """
    expire = datetime.utcnow() + timedelta(days=settings.jwt_access_token_expire_days)

    to_encode = {
        "sub": user_id,
        "email": email,
        "exp": expire,
        "iat": datetime.utcnow()
    }

    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )

    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """
    Decode and validate a JWT access token.

    Args:
        token: JWT token string

    Returns:
        Decoded token payload if valid, None otherwise
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def generate_api_key() -> tuple[str, str, str]:
    """
    Generate a new API key with hash and prefix.

    Format: recall_sk_{environment}_{64_hex_chars}

    Returns:
        Tuple of (full_key, key_hash, key_prefix)
        - full_key: Complete API key to show user once
        - key_hash: Bcrypt hash to store in database
        - key_prefix: First 16 chars for display (e.g., "recall_sk_prod_a")
    """
    # Generate random 32 bytes (64 hex chars)
    random_part = secrets.token_hex(32)

    # Use 'prod' as environment (could be configurable in future)
    environment = "prod"

    # Construct full key
    full_key = f"recall_sk_{environment}_{random_part}"

    # Hash the API key with SHA256 first (to get within bcrypt's 72-byte limit)
    # Then hash with bcrypt for secure storage
    sha256_key = hashlib.sha256(full_key.encode()).hexdigest()
    key_hash = pwd_context.hash(sha256_key)

    # Extract prefix (first 16 chars)
    key_prefix = full_key[:16]

    return full_key, key_hash, key_prefix


def verify_api_key_hash(key: str, hash: str) -> bool:
    """
    Verify an API key against its bcrypt hash.

    Args:
        key: Plain API key to verify
        hash: Bcrypt hash from database

    Returns:
        True if key matches hash, False otherwise
    """
    # Hash the API key with SHA256 first (matching generation process)
    sha256_key = hashlib.sha256(key.encode()).hexdigest()
    return pwd_context.verify(sha256_key, hash)
