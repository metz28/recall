"""
Direct database tests for API Key Management and RBAC
Tests without needing Qdrant or the full server
"""
import asyncio
import sys
sys.path.insert(0, 'backend')

from services.api_key_service import create_api_key, verify_api_key, list_api_keys, delete_api_key, toggle_api_key
from services.rbac_service import (
    create_system_roles, check_permission, get_user_permissions,
    assign_role, create_custom_role, list_roles
)
from models.api_key import ApiKeyCreate
from models.role import RoleCreate, RoleAssignmentCreate
from core.security import generate_api_key, verify_api_key_hash
from db.init_db import init_sqlite, migrate_add_users, migrate_add_api_keys, migrate_add_rbac
import uuid
import aiosqlite
from core.config import settings


async def setup_test_database():
    """Initialize database for testing"""
    print("Setting up test database...")
    await init_sqlite()
    await migrate_add_users()
    await migrate_add_api_keys()
    await migrate_add_rbac()
    print("[OK] Database initialized\n")


async def create_test_user():
    """Create a test user"""
    print("Creating test user...")

    user_id = str(uuid.uuid4())
    async with aiosqlite.connect(settings.sqlite_path) as db:
        await db.execute("""
            INSERT OR IGNORE INTO users (id, email, username, hashed_password, is_active)
            VALUES (?, ?, ?, ?, 1)
        """, (user_id, "testuser@example.com", "testuser", "dummy_hash"))
        await db.commit()

    print(f"[OK] Test user created: {user_id}\n")
    return user_id


async def test_api_key_generation():
    """Test API key generation"""
    print("=" * 60)
    print("Testing API Key Generation")
    print("=" * 60 + "\n")

    # Test key generation
    print("1. Generating API key...")
    full_key, key_hash, key_prefix = generate_api_key()

    assert full_key.startswith("recall_sk_"), "Key should start with recall_sk_"
    assert len(full_key) == 80, f"Key should be 80 chars, got {len(full_key)}"  # recall_sk_prod_ (15) + 64 hex + _ (1)
    assert len(key_prefix) == 16, f"Prefix should be 16 chars, got {len(key_prefix)}"
    print(f"[OK] API key generated: {key_prefix}...")

    # Test key hash verification
    print("\n2. Verifying API key hash...")
    assert verify_api_key_hash(full_key, key_hash), "Key should verify against hash"
    print("[OK] API key hash verification successful")

    assert not verify_api_key_hash("wrong_key", key_hash), "Wrong key should not verify"
    print("[OK] Wrong key correctly rejected\n")


async def test_api_key_service(user_id: str):
    """Test API key service functions"""
    print("=" * 60)
    print("Testing API Key Service")
    print("=" * 60 + "\n")

    # 1. Create API key
    print("1. Creating API key...")
    key_data = ApiKeyCreate(name="Test API Key")
    api_key_response = await create_api_key(user_id, key_data)

    assert api_key_response.name == "Test API Key"
    assert api_key_response.api_key.startswith("recall_sk_")
    assert api_key_response.is_active == True
    print(f"[OK] API key created: {api_key_response.key_prefix}...")

    api_key = api_key_response.api_key
    key_id = api_key_response.id

    # 2. Verify API key
    print("\n2. Verifying API key...")
    verified_user_id = await verify_api_key(api_key)
    assert verified_user_id == user_id, f"Expected user_id {user_id}, got {verified_user_id}"
    print("[OK] API key verified successfully")

    # 3. List API keys
    print("\n3. Listing API keys...")
    keys = await list_api_keys(user_id)
    assert len(keys) >= 1, "Should have at least 1 API key"
    assert any(k.id == key_id for k in keys), "Created key should be in list"
    print(f"[OK] Found {len(keys)} API key(s)")

    # 4. Disable API key
    print("\n4. Disabling API key...")
    success = await toggle_api_key(user_id, key_id, False)
    assert success, "Toggle should succeed"
    print("[OK] API key disabled")

    # 5. Verify disabled key doesn't work
    print("\n5. Verifying disabled key is rejected...")
    verified_user_id = await verify_api_key(api_key)
    assert verified_user_id is None, "Disabled key should not verify"
    print("[OK] Disabled key correctly rejected")

    # 6. Re-enable API key
    print("\n6. Re-enabling API key...")
    success = await toggle_api_key(user_id, key_id, True)
    assert success, "Toggle should succeed"
    verified_user_id = await verify_api_key(api_key)
    assert verified_user_id == user_id, "Re-enabled key should verify"
    print("[OK] API key re-enabled and working")

    # 7. Delete API key
    print("\n7. Deleting API key...")
    success = await delete_api_key(user_id, key_id)
    assert success, "Delete should succeed"
    print("[OK] API key deleted")

    # 8. Verify deleted key doesn't work
    print("\n8. Verifying deleted key is rejected...")
    verified_user_id = await verify_api_key(api_key)
    assert verified_user_id is None, "Deleted key should not verify"
    print("[OK] Deleted key correctly rejected\n")


async def test_rbac_system_roles():
    """Test RBAC system roles"""
    print("=" * 60)
    print("Testing RBAC System Roles")
    print("=" * 60 + "\n")

    # 1. Create system roles
    print("1. Creating system roles...")
    await create_system_roles()
    print("[OK] System roles created")

    # 2. List roles
    print("\n2. Listing roles...")
    roles = await list_roles()
    assert len(roles) >= 5, "Should have at least 5 system roles"

    role_names = [r.name for r in roles]
    assert "viewer" in role_names
    assert "editor" in role_names
    assert "analyst" in role_names
    assert "admin" in role_names
    assert "owner" in role_names
    print(f"[OK] Found {len(roles)} role(s):")
    for role in roles:
        print(f"  - {role.display_name}: {len(role.permissions)} permissions")

    # 3. Check role permissions
    print("\n3. Checking role permissions...")
    viewer_role = next(r for r in roles if r.name == "viewer")
    assert "document:read" in viewer_role.permissions
    assert "search:execute" in viewer_role.permissions
    print(f"[OK] Viewer role has correct permissions: {viewer_role.permissions}")

    owner_role = next(r for r in roles if r.name == "owner")
    assert "*:*" in owner_role.permissions
    print(f"[OK] Owner role has wildcard permission: {owner_role.permissions}\n")

    return roles


async def test_custom_roles(user_id: str):
    """Test custom role creation"""
    print("=" * 60)
    print("Testing Custom Roles")
    print("=" * 60 + "\n")

    # 1. Create custom role
    print("1. Creating custom role...")
    role_data = RoleCreate(
        name="custom_reader",
        display_name="Custom Reader",
        description="Read-only access with search",
        permissions=["document:read", "search:execute"]
    )

    custom_role = await create_custom_role(user_id, role_data)
    assert custom_role.name == "custom_reader"
    assert custom_role.is_custom == True
    assert custom_role.is_system == False
    assert len(custom_role.permissions) == 2
    print(f"[OK] Custom role created: {custom_role.display_name}")

    # 2. List roles again
    print("\n2. Listing all roles...")
    roles = await list_roles()
    assert any(r.name == "custom_reader" for r in roles), "Custom role should be in list"
    print(f"[OK] Custom role appears in list ({len(roles)} total roles)\n")

    return custom_role


async def test_permission_checking(user_id: str, roles: list):
    """Test permission checking"""
    print("=" * 60)
    print("Testing Permission Checking")
    print("=" * 60 + "\n")

    # Create a test document owned by user
    print("1. Creating test document...")
    doc_id = str(uuid.uuid4())
    async with aiosqlite.connect(settings.sqlite_path) as db:
        await db.execute("""
            INSERT INTO documents (id, title, source_type, user_id)
            VALUES (?, ?, ?, ?)
        """, (doc_id, "Test Document", "text", user_id))
        await db.commit()
    print(f"[OK] Test document created: {doc_id}")

    # 2. Check owner permissions (should have all)
    print("\n2. Checking owner permissions...")
    has_read = await check_permission(user_id, "document", doc_id, "document:read")
    has_write = await check_permission(user_id, "document", doc_id, "document:write")
    has_delete = await check_permission(user_id, "document", doc_id, "document:delete")

    assert has_read, "Owner should have read permission"
    assert has_write, "Owner should have write permission"
    assert has_delete, "Owner should have delete permission"
    print("[OK] Owner has all permissions (via ownership)")

    # 3. Get all user permissions
    print("\n3. Getting all owner permissions...")
    permissions = await get_user_permissions(user_id, "document", doc_id)
    assert "*:*" in permissions, "Owner should have wildcard permission"
    print(f"[OK] Owner permissions: {permissions}")

    # 4. Create second user
    print("\n4. Creating second test user...")
    user2_id = str(uuid.uuid4())
    async with aiosqlite.connect(settings.sqlite_path) as db:
        await db.execute("""
            INSERT INTO users (id, email, username, hashed_password, is_active)
            VALUES (?, ?, ?, ?, 1)
        """, (user2_id, "user2@example.com", "user2", "dummy_hash"))
        await db.commit()
    print(f"[OK] Second user created: {user2_id}")

    # 5. Check user2 permissions (should have none)
    print("\n5. Checking non-owner permissions (before assignment)...")
    has_permission = await check_permission(user2_id, "document", doc_id, "document:read")
    assert not has_permission, "Non-owner should not have permission by default"
    print("[OK] Non-owner correctly has no permissions")

    # 6. Assign viewer role to user2
    print("\n6. Assigning viewer role to second user...")
    viewer_role = next(r for r in roles if r.name == "viewer")
    assignment_data = RoleAssignmentCreate(
        role_id=viewer_role.id,
        user_id=user2_id,
        resource_type="document",
        resource_id=doc_id
    )

    assignment = await assign_role(user_id, assignment_data)
    assert assignment.user_id == user2_id
    assert assignment.role_name == "viewer"
    print("[OK] Viewer role assigned to second user")

    # 7. Check user2 permissions (should have read)
    print("\n7. Checking permissions after role assignment...")
    has_read = await check_permission(user2_id, "document", doc_id, "document:read")
    has_write = await check_permission(user2_id, "document", doc_id, "document:write")

    assert has_read, "User with viewer role should have read permission"
    assert not has_write, "User with viewer role should not have write permission"
    print("[OK] Role permissions working correctly")

    # 8. Get user2 permissions
    print("\n8. Getting all assigned user permissions...")
    permissions = await get_user_permissions(user2_id, "document", doc_id)
    print(f"[OK] User permissions: {permissions}")
    assert "document:read" in permissions
    assert "search:execute" in permissions
    print("[OK] Permission checking complete\n")


async def run_all_tests():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("API Key Management & RBAC - Database Tests")
    print("=" * 60 + "\n")

    try:
        # Setup
        await setup_test_database()
        user_id = await create_test_user()

        # Run tests
        await test_api_key_generation()
        await test_api_key_service(user_id)
        roles = await test_rbac_system_roles()
        await test_custom_roles(user_id)
        await test_permission_checking(user_id, roles)

        print("=" * 60)
        print("[PASS] All Tests Passed!")
        print("=" * 60 + "\n")

    except AssertionError as e:
        print(f"\n[FAIL] Test failed: {e}")
        raise
    except Exception as e:
        print(f"\n[FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        raise


if __name__ == "__main__":
    asyncio.run(run_all_tests())
