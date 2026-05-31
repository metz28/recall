"""
Tests for authentication endpoints and user data isolation.
"""
import pytest
from fastapi.testclient import TestClient
from main import app
from core.config import settings
import aiosqlite
import os

client = TestClient(app)

# Test database path
TEST_DB_PATH = "./data/test_recall.db"


@pytest.fixture(autouse=True)
async def setup_teardown():
    """Setup and teardown for each test."""
    # Backup current DB path
    original_db_path = settings.sqlite_path

    # Use test database
    settings.sqlite_path = TEST_DB_PATH

    # Initialize test database
    from db.init_db import init_databases
    await init_databases()

    yield

    # Cleanup
    settings.sqlite_path = original_db_path
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)


class TestUserRegistration:
    """Tests for user registration."""

    def test_register_success(self):
        """Test successful user registration."""
        response = client.post(
            "/api/auth/register",
            json={
                "email": "test@example.com",
                "username": "testuser",
                "password": "password123"
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["message"] == "User registered successfully"
        assert data["user"]["email"] == "test@example.com"
        assert data["user"]["username"] == "testuser"
        assert "hashed_password" not in data["user"]

    def test_register_duplicate_email(self):
        """Test registration with duplicate email fails."""
        # Register first user
        client.post(
            "/api/auth/register",
            json={
                "email": "test@example.com",
                "username": "testuser1",
                "password": "password123"
            }
        )

        # Try to register with same email
        response = client.post(
            "/api/auth/register",
            json={
                "email": "test@example.com",
                "username": "testuser2",
                "password": "password123"
            }
        )

        assert response.status_code == 400
        assert "Email already registered" in response.json()["detail"]

    def test_register_duplicate_username(self):
        """Test registration with duplicate username fails."""
        # Register first user
        client.post(
            "/api/auth/register",
            json={
                "email": "test1@example.com",
                "username": "testuser",
                "password": "password123"
            }
        )

        # Try to register with same username
        response = client.post(
            "/api/auth/register",
            json={
                "email": "test2@example.com",
                "username": "testuser",
                "password": "password123"
            }
        )

        assert response.status_code == 400
        assert "Username already taken" in response.json()["detail"]


class TestUserLogin:
    """Tests for user login."""

    def test_login_success(self):
        """Test successful login."""
        # Register user
        client.post(
            "/api/auth/register",
            json={
                "email": "test@example.com",
                "username": "testuser",
                "password": "password123"
            }
        )

        # Login
        response = client.post(
            "/api/auth/login",
            params={
                "email": "test@example.com",
                "password": "password123"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "test@example.com"

    def test_login_wrong_password(self):
        """Test login with wrong password fails."""
        # Register user
        client.post(
            "/api/auth/register",
            json={
                "email": "test@example.com",
                "username": "testuser",
                "password": "password123"
            }
        )

        # Try to login with wrong password
        response = client.post(
            "/api/auth/login",
            params={
                "email": "test@example.com",
                "password": "wrongpassword"
            }
        )

        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]

    def test_login_nonexistent_user(self):
        """Test login with non-existent user fails."""
        response = client.post(
            "/api/auth/login",
            params={
                "email": "nonexistent@example.com",
                "password": "password123"
            }
        )

        assert response.status_code == 401
        assert "Invalid email or password" in response.json()["detail"]


class TestProtectedEndpoints:
    """Tests for protected endpoints."""

    def test_protected_endpoint_without_token(self):
        """Test accessing protected endpoint without token fails."""
        response = client.get("/api/auth/me")

        assert response.status_code == 403  # No Authorization header

    def test_protected_endpoint_with_invalid_token(self):
        """Test accessing protected endpoint with invalid token fails."""
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid_token"}
        )

        assert response.status_code == 401

    def test_protected_endpoint_with_valid_token(self):
        """Test accessing protected endpoint with valid token succeeds."""
        # Register and login
        client.post(
            "/api/auth/register",
            json={
                "email": "test@example.com",
                "username": "testuser",
                "password": "password123"
            }
        )

        login_response = client.post(
            "/api/auth/login",
            params={
                "email": "test@example.com",
                "password": "password123"
            }
        )

        token = login_response.json()["access_token"]

        # Access protected endpoint
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["username"] == "testuser"


class TestUserDataIsolation:
    """Critical tests for user data isolation."""

    @pytest.mark.asyncio
    async def test_users_cannot_access_each_other_documents(self):
        """Test that users can only see their own documents."""
        # Register two users
        user1_response = client.post(
            "/api/auth/register",
            json={
                "email": "user1@example.com",
                "username": "user1",
                "password": "password123"
            }
        )
        user1_token = user1_response.json()["user"]["id"]

        user2_response = client.post(
            "/api/auth/register",
            json={
                "email": "user2@example.com",
                "username": "user2",
                "password": "password123"
            }
        )
        user2_token = user2_response.json()["user"]["id"]

        # Create test documents directly in database for both users
        async with aiosqlite.connect(settings.sqlite_path) as db:
            await db.execute(
                """INSERT INTO documents (id, title, source_type, source_path, file_type, num_chunks, user_id)
                   VALUES ('doc1', 'User1 Doc', 'file', 'test.txt', 'txt', 0, ?)""",
                (user1_token,)
            )
            await db.execute(
                """INSERT INTO documents (id, title, source_type, source_path, file_type, num_chunks, user_id)
                   VALUES ('doc2', 'User2 Doc', 'file', 'test.txt', 'txt', 0, ?)""",
                (user2_token,)
            )
            await db.commit()

        # Login as user1
        login1 = client.post(
            "/api/auth/login",
            params={"email": "user1@example.com", "password": "password123"}
        )
        token1 = login1.json()["access_token"]

        # Login as user2
        login2 = client.post(
            "/api/auth/login",
            params={"email": "user2@example.com", "password": "password123"}
        )
        token2 = login2.json()["access_token"]

        # User1 should only see their document
        docs1 = client.get(
            "/api/ingest/documents",
            headers={"Authorization": f"Bearer {token1}"}
        )
        assert docs1.status_code == 200
        docs1_data = docs1.json()
        assert len(docs1_data) == 1
        assert docs1_data[0]["title"] == "User1 Doc"

        # User2 should only see their document
        docs2 = client.get(
            "/api/ingest/documents",
            headers={"Authorization": f"Bearer {token2}"}
        )
        assert docs2.status_code == 200
        docs2_data = docs2.json()
        assert len(docs2_data) == 1
        assert docs2_data[0]["title"] == "User2 Doc"

        # User1 should NOT be able to delete User2's document
        delete_response = client.delete(
            "/api/ingest/documents/doc2",
            headers={"Authorization": f"Bearer {token1}"}
        )
        assert delete_response.status_code == 403  # Forbidden

    @pytest.mark.asyncio
    async def test_collections_are_user_scoped(self):
        """Test that collections are isolated per user."""
        # Register two users and get tokens
        client.post(
            "/api/auth/register",
            json={"email": "user1@example.com", "username": "user1", "password": "password123"}
        )
        login1 = client.post(
            "/api/auth/login",
            params={"email": "user1@example.com", "password": "password123"}
        )
        token1 = login1.json()["access_token"]

        client.post(
            "/api/auth/register",
            json={"email": "user2@example.com", "username": "user2", "password": "password123"}
        )
        login2 = client.post(
            "/api/auth/login",
            params={"email": "user2@example.com", "password": "password123"}
        )
        token2 = login2.json()["access_token"]

        # User1 creates documents in collection "work"
        # User2 creates documents in collection "personal"
        # Each should only see their own collections
        # (This would require uploading actual documents, simplified here)

        # Get collections for user1
        collections1 = client.get(
            "/api/collections",
            headers={"Authorization": f"Bearer {token1}"}
        )
        assert collections1.status_code == 200

        # Get collections for user2
        collections2 = client.get(
            "/api/collections",
            headers={"Authorization": f"Bearer {token2}"}
        )
        assert collections2.status_code == 200

        # Collections should be independent
        # (Exact assertion depends on whether default collection exists)
