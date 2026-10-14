"""
Tests for conversation ownership and isolation.

AC verified:
  3. Students cannot access another student's conversations.
  7-no-docs. When no documents are ready, message returns insufficient_evidence.
"""
import uuid
import pytest
from httpx import AsyncClient

from tests.conftest import register_and_login


def uid():
    return uuid.uuid4().hex[:8]


@pytest.mark.asyncio
async def test_create_and_list_conversations(client: AsyncClient):
    """A student can create and list their own conversations."""
    await register_and_login(client)
    create_res = await client.post("/api/conversations")
    assert create_res.status_code == 201
    conv_id = create_res.json()["id"]

    list_res = await client.get("/api/conversations")
    assert list_res.status_code == 200
    ids = [c["id"] for c in list_res.json()["items"]]
    assert conv_id in ids


@pytest.mark.asyncio
async def test_get_conversation_detail(client: AsyncClient):
    """Student can retrieve their own conversation detail."""
    await register_and_login(client)
    r = await client.post("/api/conversations")
    conv_id = r.json()["id"]
    res = await client.get(f"/api/conversations/{conv_id}")
    assert res.status_code == 200
    assert res.json()["id"] == conv_id


@pytest.mark.asyncio
async def test_student_cannot_read_other_students_conversation(client: AsyncClient):
    """
    Student A creates a conversation; when Student B logs in to the same
    client (cookie replaced), they cannot see A's conversation.
    """
    email_a = f"a_{uid()}@test.edu"
    email_b = f"b_{uid()}@test.edu"

    # Log in as A, create conversation
    await register_and_login(client, email_a)
    r = await client.post("/api/conversations")
    assert r.status_code == 201
    conv_id_a = r.json()["id"]

    # Log in as B (replaces cookie)
    await client.post("/api/auth/logout")
    await register_and_login(client, email_b)

    # B tries to read A's conversation
    res = await client.get(f"/api/conversations/{conv_id_a}")
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_delete_conversation(client: AsyncClient):
    """A student can delete their own conversation."""
    await register_and_login(client)
    r = await client.post("/api/conversations")
    conv_id = r.json()["id"]

    del_res = await client.delete(f"/api/conversations/{conv_id}")
    assert del_res.status_code == 200

    get_res = await client.get(f"/api/conversations/{conv_id}")
    assert get_res.status_code == 404


@pytest.mark.asyncio
async def test_ask_with_no_documents_returns_notice(client: AsyncClient):
    """
    Posting a message when no ready documents exist should return a notice
    with insufficient_evidence=True rather than raising an error.
    """
    await register_and_login(client)
    r = await client.post("/api/conversations")
    conv_id = r.json()["id"]

    ask_res = await client.post(
        f"/api/conversations/{conv_id}/messages",
        json={"question": "What is the attendance rule?"},
    )
    assert ask_res.status_code == 200
    data = ask_res.json()
    assert data["insufficient_evidence"] is True
    content = data["answer"].lower()
    assert "administrator" in content or "document" in content or "upload" in content
