"""Authentication API endpoints."""
import uuid
import aiosqlite
from fastapi import APIRouter, HTTPException, Depends, status

from core.config import settings
from core.dependencies import get_current_user
from core.security import hash_password, verify_password, create_access_token
from models.user import User, UserCreate, UserResponse
from core.logging_config import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.post("/register", response_model=dict, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate):
    """
    Register a new user account.

    Args:
        user_data: User registration data (email, username, password)

    Returns:
        Success message with user info

    Raises:
        HTTPException: 400 if email or username already exists
    """
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row

        # Check if email already exists
        cursor = await db.execute(
            "SELECT id FROM users WHERE email = ?",
            (user_data.email,)
        )
        if await cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

        # Check if username already exists
        cursor = await db.execute(
            "SELECT id FROM users WHERE username = ?",
            (user_data.username,)
        )
        if await cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )

        # Create new user
        user_id = str(uuid.uuid4())
        hashed_pw = hash_password(user_data.password)

        await db.execute(
            """
            INSERT INTO users (id, email, username, hashed_password, is_active)
            VALUES (?, ?, ?, ?, 1)
            """,
            (user_id, user_data.email, user_data.username, hashed_pw)
        )
        await db.commit()

        # Fetch created user
        cursor = await db.execute(
            "SELECT id, email, username, created_at, is_active FROM users WHERE id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()

        logger.info(f"New user registered: {user_data.username} ({user_data.email})")

        return {
            "message": "User registered successfully",
            "user": {
                "id": row["id"],
                "email": row["email"],
                "username": row["username"],
                "created_at": row["created_at"],
                "is_active": bool(row["is_active"])
            }
        }


@router.post("/login", response_model=dict)
async def login(email: str, password: str):
    """
    Login with email and password to receive JWT token.

    Args:
        email: User email
        password: User password

    Returns:
        JWT access token and user info

    Raises:
        HTTPException: 401 if credentials are invalid
    """
    async with aiosqlite.connect(settings.sqlite_path) as db:
        db.row_factory = aiosqlite.Row

        # Fetch user by email
        cursor = await db.execute(
            "SELECT * FROM users WHERE email = ? AND is_active = 1",
            (email,)
        )
        row = await cursor.fetchone()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        # Verify password
        if not verify_password(password, row["hashed_password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        # Create access token
        access_token = create_access_token(
            user_id=row["id"],
            email=row["email"]
        )

        logger.info(f"User logged in: {row['username']} ({email})")

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": row["id"],
                "email": row["email"],
                "username": row["username"],
                "created_at": row["created_at"],
                "is_active": bool(row["is_active"])
            }
        }


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """
    Get current authenticated user information.

    Args:
        current_user: Current user from JWT token (injected by dependency)

    Returns:
        Current user information
    """
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        created_at=current_user.created_at,
        is_active=current_user.is_active
    )


@router.post("/logout")
async def logout():
    """
    Logout endpoint (client-side token removal).

    This is mainly a placeholder for REST API completeness.
    Actual logout happens client-side by removing the JWT token.

    Returns:
        Success message
    """
    return {"message": "Logged out successfully"}
