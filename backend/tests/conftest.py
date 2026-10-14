"""
Test configuration and shared fixtures.

Uses a named temp file SQLite database per-test so each test is fully isolated
(StaticPool with :memory: reuses the same connection pool across all engine
instances in the same process, causing data bleed-through).

Heavy dependencies (Sentence Transformers, FAISS, Groq) are mocked.
"""
import asyncio
import os
import tempfile
import uuid
from typing import AsyncGenerator
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Set environment BEFORE any app import
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///test_placeholder.db"
os.environ["SYNC_DATABASE_URL"] = "sqlite:///test_placeholder.db"
os.environ["SECRET_KEY"] = "test-secret-key-32chars-xxxxxxxxx"
os.environ["GROQ_API_KEY"] = "gsk_test_key"
os.environ["UPLOAD_DIR"] = "/tmp/cp_test_uploads"
os.environ["FAISS_INDEX_DIR"] = "/tmp/cp_test_faiss"

from app.database import Base, get_db  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def client(tmp_path) -> AsyncGenerator[AsyncClient, None]:
    """
    Each test gets a unique SQLite file database for full isolation.
    FAISS index manager is mocked; Groq is never called.
    """
    db_file = tmp_path / f"test_{uuid.uuid4().hex}.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"

    engine = create_async_engine(db_url, connect_args={"check_same_thread": False})
    Session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def _override_db():
        async with Session() as session:
            yield session

    fastapi_app.dependency_overrides[get_db] = _override_db

    mock_mgr = MagicMock()
    mock_mgr.total_vectors = 0
    mock_mgr.search.return_value = []
    mock_mgr.add_chunks.return_value = None
    mock_mgr.remove_chunks.return_value = None
    mock_mgr.rebuild.return_value = None

    with patch("app.rag.index_manager.get_index_manager", return_value=mock_mgr):
        async with AsyncClient(
            transport=ASGITransport(app=fastapi_app), base_url="http://test"
        ) as ac:
            yield ac

    fastapi_app.dependency_overrides.clear()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(client: AsyncClient) -> AsyncGenerator[AsyncSession, None]:
    """Yields a session from the same DB the client fixture uses."""
    override = fastapi_app.dependency_overrides.get(get_db)
    if override is None:
        raise RuntimeError("db_session requires the client fixture")
    async for session in override():
        yield session
        break


# ── Helpers ───────────────────────────────────────────────────────────────────

async def register_and_login(
    client: AsyncClient,
    email: str | None = None,
    password: str = "TestPass1!",
) -> dict:
    if email is None:
        email = f"user_{uuid.uuid4().hex[:8]}@test.edu"
    res = await client.post(
        "/api/auth/register",
        json={"email": email, "name": "Test User", "password": password},
    )
    assert res.status_code == 201, f"register failed ({res.status_code}): {res.text}"
    return res.json()


async def create_admin_user(db_session: AsyncSession, email: str | None = None):
    from app.models.user import User, UserRole
    from app.services.auth_service import hash_password

    if email is None:
        email = f"admin_{uuid.uuid4().hex[:8]}@test.edu"
    user = User(
        email=email,
        name="Test Admin",
        hashed_password=hash_password("AdminPass1!"),
        role=UserRole.admin,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user
