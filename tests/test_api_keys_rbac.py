"""
Test script for API Key Management and RBAC
"""
import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_api_keys():
    """Test API Key Management functionality"""
    print("=" * 60)
    print("Testing API Key Management")
    print("=" * 60)

    # 1. Register a test user
    print("\n1. Registering test user...")
    register_data = {
        "email": "test@example.com",
        "username": "testuser",
        "password": "testpassword123"
    }

    response = requests.post(f"{BASE_URL}/api/auth/register", json=register_data)
    if response.status_code == 201:
        print("✓ User registered successfully")
    elif response.status_code == 400 and "already" in response.text:
        print("✓ User already exists, continuing...")
    else:
        print(f"✗ Failed to register user: {response.text}")
        return

    # 2. Login
    print("\n2. Logging in...")
    login_response = requests.post(
        f"{BASE_URL}/api/auth/login",
        params={"email": "test@example.com", "password": "testpassword123"}
    )

    if login_response.status_code != 200:
        print(f"✗ Login failed: {login_response.text}")
        return

    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("✓ Login successful")

    # 3. Create an API key
    print("\n3. Creating API key...")
    api_key_data = {
        "name": "Test API Key"
    }

    response = requests.post(
        f"{BASE_URL}/api/v1/api-keys",
        json=api_key_data,
        headers=headers
    )

    if response.status_code != 201:
        print(f"✗ Failed to create API key: {response.text}")
        return

    api_key_response = response.json()
    api_key = api_key_response["api_key"]
    key_id = api_key_response["id"]
    print(f"✓ API key created: {api_key_response['key_prefix']}...")
    print(f"  Full key (save this): {api_key[:20]}...")

    # 4. List API keys
    print("\n4. Listing API keys...")
    response = requests.get(f"{BASE_URL}/api/v1/api-keys", headers=headers)

    if response.status_code != 200:
        print(f"✗ Failed to list API keys: {response.text}")
        return

    keys = response.json()["api_keys"]
    print(f"✓ Found {len(keys)} API key(s)")
    for key in keys:
        print(f"  - {key['name']}: {key['key_prefix']}...")

    # 5. Test authentication with API key
    print("\n5. Testing authentication with API key...")
    api_key_headers = {"Authorization": f"Bearer {api_key}"}

    response = requests.get(f"{BASE_URL}/api/auth/me", headers=api_key_headers)

    if response.status_code != 200:
        print(f"✗ API key authentication failed: {response.text}")
        return

    user_data = response.json()
    print(f"✓ API key authentication successful")
    print(f"  User: {user_data['username']} ({user_data['email']})")

    # 6. Disable API key
    print("\n6. Disabling API key...")
    response = requests.put(
        f"{BASE_URL}/api/v1/api-keys/{key_id}/toggle",
        json={"is_active": False},
        headers=headers
    )

    if response.status_code != 200:
        print(f"✗ Failed to disable API key: {response.text}")
        return

    print("✓ API key disabled")

    # 7. Test that disabled key doesn't work
    print("\n7. Verifying disabled key cannot authenticate...")
    response = requests.get(f"{BASE_URL}/api/auth/me", headers=api_key_headers)

    if response.status_code == 401:
        print("✓ Disabled API key correctly rejected")
    else:
        print(f"✗ Disabled key still works (unexpected)")

    # 8. Re-enable API key
    print("\n8. Re-enabling API key...")
    response = requests.put(
        f"{BASE_URL}/api/v1/api-keys/{key_id}/toggle",
        json={"is_active": True},
        headers=headers
    )

    if response.status_code == 200:
        print("✓ API key re-enabled")

    # 9. Delete API key
    print("\n9. Deleting API key...")
    response = requests.delete(
        f"{BASE_URL}/api/v1/api-keys/{key_id}",
        headers=headers
    )

    if response.status_code == 204:
        print("✓ API key deleted")
    else:
        print(f"✗ Failed to delete API key: {response.text}")

    print("\n" + "=" * 60)
    print("API Key Management Tests Complete!")
    print("=" * 60)


def test_rbac():
    """Test RBAC functionality"""
    print("\n\n" + "=" * 60)
    print("Testing Role-Based Access Control (RBAC)")
    print("=" * 60)

    # Login as test user
    print("\n1. Logging in as test user...")
    login_response = requests.post(
        f"{BASE_URL}/api/auth/login",
        params={"email": "test@example.com", "password": "testpassword123"}
    )

    if login_response.status_code != 200:
        print(f"✗ Login failed: {login_response.text}")
        return

    token = login_response.json()["access_token"]
    user_id = login_response.json()["user"]["id"]
    headers = {"Authorization": f"Bearer {token}"}
    print("✓ Login successful")

    # 2. List system roles
    print("\n2. Listing system roles...")
    response = requests.get(f"{BASE_URL}/api/v1/roles", headers=headers)

    if response.status_code != 200:
        print(f"✗ Failed to list roles: {response.text}")
        return

    roles = response.json()["roles"]
    print(f"✓ Found {len(roles)} role(s)")
    for role in roles:
        print(f"  - {role['display_name']}: {len(role['permissions'])} permissions")

    # Store viewer role ID for later
    viewer_role_id = next((r['id'] for r in roles if r['name'] == 'viewer'), None)

    # 3. Create a custom role
    print("\n3. Creating custom role...")
    custom_role_data = {
        "name": "custom_reader",
        "display_name": "Custom Reader",
        "description": "Read documents and search only",
        "permissions": ["document:read", "search:execute"]
    }

    response = requests.post(
        f"{BASE_URL}/api/v1/roles",
        json=custom_role_data,
        headers=headers
    )

    if response.status_code != 201:
        print(f"✗ Failed to create custom role: {response.text}")
        custom_role_id = None
    else:
        custom_role = response.json()
        custom_role_id = custom_role["id"]
        print(f"✓ Custom role created: {custom_role['display_name']}")

    # 4. Register a second user for collaboration testing
    print("\n4. Registering second user...")
    register_data = {
        "email": "collaborator@example.com",
        "username": "collaborator",
        "password": "testpassword123"
    }

    response = requests.post(f"{BASE_URL}/api/auth/register", json=register_data)
    if response.status_code == 201:
        collab_user_id = response.json()["user"]["id"]
        print("✓ Collaborator registered successfully")
    elif response.status_code == 400 and "already" in response.text:
        # Get user ID
        login_response = requests.post(
            f"{BASE_URL}/api/auth/login",
            params={"email": "collaborator@example.com", "password": "testpassword123"}
        )
        collab_user_id = login_response.json()["user"]["id"]
        print("✓ Collaborator already exists")
    else:
        print(f"✗ Failed to register collaborator: {response.text}")
        collab_user_id = None

    # 5. Check user permissions (should have none for a non-existent document)
    print("\n5. Checking user permissions...")
    check_data = {
        "user_id": user_id,
        "resource_type": "document",
        "resource_id": "test-doc-123",
        "permission": "document:read"
    }

    response = requests.post(
        f"{BASE_URL}/api/v1/permissions/check",
        json=check_data,
        headers=headers
    )

    if response.status_code == 200:
        result = response.json()
        print(f"✓ Permission check completed")
        print(f"  Has permission: {result['has_permission']}")
        print(f"  Granted permissions: {result['granted_permissions']}")
    else:
        print(f"✗ Permission check failed: {response.text}")

    # 6. List role assignments for user
    print("\n6. Listing role assignments for user...")
    response = requests.get(
        f"{BASE_URL}/api/v1/role-assignments/user/{user_id}",
        headers=headers
    )

    if response.status_code == 200:
        assignments = response.json()["assignments"]
        print(f"✓ Found {len(assignments)} role assignment(s)")
        for assignment in assignments:
            print(f"  - {assignment['role_display_name']} on {assignment['resource_type']}")
    else:
        print(f"✗ Failed to list role assignments: {response.text}")

    # 7. Update custom role (if created)
    if custom_role_id:
        print("\n7. Updating custom role...")
        update_data = {
            "description": "Updated: Read documents and search with export"
        }

        response = requests.put(
            f"{BASE_URL}/api/v1/roles/{custom_role_id}",
            json=update_data,
            headers=headers
        )

        if response.status_code == 200:
            print("✓ Custom role updated")
        else:
            print(f"✗ Failed to update role: {response.text}")

    # 8. Delete custom role (if created)
    if custom_role_id:
        print("\n8. Deleting custom role...")
        response = requests.delete(
            f"{BASE_URL}/api/v1/roles/{custom_role_id}",
            headers=headers
        )

        if response.status_code == 204:
            print("✓ Custom role deleted")
        else:
            print(f"✗ Failed to delete role: {response.text}")

    print("\n" + "=" * 60)
    print("RBAC Tests Complete!")
    print("=" * 60)


if __name__ == "__main__":
    print("\nStarting API Key Management and RBAC Tests...")
    print("Make sure the server is running on http://localhost:8000")
    print("\nWaiting 3 seconds for server to be ready...")
    time.sleep(3)

    try:
        # Check if server is running
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✓ Server is running\n")
        else:
            print("✗ Server returned unexpected status")
            exit(1)
    except requests.exceptions.RequestException as e:
        print(f"✗ Cannot connect to server: {e}")
        print("Please start the server with: cd backend && python -m uvicorn main:app --reload")
        exit(1)

    # Run tests
    test_api_keys()
    test_rbac()

    print("\n\n✅ All tests completed successfully!")
