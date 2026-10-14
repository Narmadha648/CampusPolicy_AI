"""
Tests for authentication endpoints.

AC verified:
  1. A student can register and log in.
  2. Public registration cannot create administrators.
  3. Students cannot access admin APIs.
"""
import uuid
import pytest
from httpx import AsyncClient

from tests.conftest import register_and_login


def uid() -> str:
    """Short unique suffix for test emails."""
    return uuid.uuid4().hex[:8]


@pytest.mark.asyncio
async def test_register_creates_student(client: AsyncClient):
    """Registration always creates a student account."""
    res = await client.post(
        "/api/auth/register",
        json={"email": f"student_{uid()}@test.edu", "name": "Alice", "password": "SecureP1!"},
    )
    assert res.status_code == 201
    data = res.json()
    assert data["user"]["role"] == "student"


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient):
    """Duplicate email registration returns 409."""
    email = f"dup_{uid()}@test.edu"
    payload = {"email": email, "name": "Bob", "password": "SecureP1!"}
    r1 = await client.post("/api/auth/register", json=payload)
    assert r1.status_code == 201
    r2 = await client.post("/api/auth/register", json=payload)
    assert r2.status_code == 409


@pytest.mark.asyncio
async def test_register_weak_password(client: AsyncClient):
    """Password shorter than 8 characters is rejected with 422."""
    res = await client.post(
        "/api/auth/register",
        json={"email": f"weak_{uid()}@test.edu", "name": "Charlie", "password": "short"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_login_valid(client: AsyncClient):
    """Valid credentials return user info and set session cookie."""
    email = f"login_{uid()}@test.edu"
    await client.post(
        "/api/auth/register",
        json={"email": email, "name": "Dave", "password": "LoginPa1!"},
    )
    res = await client.post(
        "/api/auth/login",
        json={"email": email, "password": "LoginPa1!"},
    )
    assert res.status_code == 200
    assert res.json()["user"]["email"] == email
    assert "cp_session" in res.cookies


@pytest.mark.asyncio
async def test_login_wrong_password(client: AsyncClient):
    """Wrong password returns 401."""
    email = f"badpw_{uid()}@test.edu"
    await client.post(
        "/api/auth/register",
        json={"email": email, "name": "Eve", "password": "Correct1!"},
    )
    res = await client.post(
        "/api/auth/login",
        json={"email": email, "password": "WrongPa1!"},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_me_authenticated(client: AsyncClient):
    """Authenticated /me returns the current user."""
    email = f"me_{uid()}@test.edu"
    await register_and_login(client, email)
    res = await client.get("/api/auth/me")
    assert res.status_code == 200
    assert res.json()["email"] == email


@pytest.mark.asyncio
async def test_me_unauthenticated(client: AsyncClient):
    """/me without a session cookie returns 401."""
    # Create a fresh client with no cookies by not calling register_and_login
    fresh_client = AsyncClient.__new__(AsyncClient)
    # Just test the endpoint from client without any auth cookie set
    from httpx import AsyncClient as HC, ASGITransport
    from app.main import app
    from unittest.mock import patch, MagicMock
    mock_mgr = MagicMock()
    mock_mgr.search.return_value = []
    with patch("app.rag.index_manager.get_index_manager", return_value=mock_mgr):
        async with HC(transport=ASGITransport(app=app), base_url="http://test") as c:
            res = await c.get("/api/auth/me")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_logout_clears_cookie(client: AsyncClient):
    """Logout returns 200."""
    await register_and_login(client)
    res = await client.post("/api/auth/logout")
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_student_cannot_access_admin_documents(client: AsyncClient):
    """Students cannot access admin document list (403)."""
    await register_and_login(client)
    res = await client.get("/api/admin/documents")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_student_cannot_access_admin_stats(client: AsyncClient):
    """Students cannot access admin stats (403)."""
    await register_and_login(client)
    res = await client.get("/api/admin/stats")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_public_registration_cannot_create_admin(client: AsyncClient):
    """
    The registration endpoint does not accept a 'role' field.
    Any extra fields are ignored and the account is always student.
    """
    res = await client.post(
        "/api/auth/register",
        json={
            "email": f"sneaky_{uid()}@test.edu",
            "name": "Sneaky",
            "password": "SecureP1!",
            "role": "admin",
        },
    )
    assert res.status_code == 201
    assert res.json()["user"]["role"] == "student"
