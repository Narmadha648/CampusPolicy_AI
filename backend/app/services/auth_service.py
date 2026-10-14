"""Authentication service: password hashing, session management."""
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt as _bcrypt_lib
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.user import AuthSession, User, UserRole

logger = logging.getLogger(__name__)
settings = get_settings()

SESSION_COOKIE = "cp_session"


def hash_password(plain: str) -> str:
    """Hash a password with bcrypt (compatible with bcrypt 3.x–5.x)."""
    return _bcrypt_lib.hashpw(plain.encode("utf-8"), _bcrypt_lib.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against its bcrypt hash."""
    try:
        return _bcrypt_lib.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def _hash_token(token: str) -> str:
    """Store only a SHA-256 hash of the session token — never the raw token."""
    return hashlib.sha256(token.encode()).hexdigest()


async def create_session(
    db: AsyncSession,
    user: User,
    user_agent: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> str:
    """Creates an auth session, returns the raw (unhashed) token."""
    token = secrets.token_urlsafe(48)
    token_hash = _hash_token(token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.session_expire_days)
    session = AuthSession(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    db.add(session)
    await db.commit()
    return token


async def get_user_from_token(db: AsyncSession, token: str) -> Optional[User]:
    """Validates token and returns the associated active user."""
    token_hash = _hash_token(token)
    now = datetime.now(timezone.utc)
    result = await db.execute(
        select(AuthSession)
        .where(AuthSession.token_hash == token_hash)
        .where(AuthSession.expires_at > now)
    )
    session: Optional[AuthSession] = result.scalar_one_or_none()
    if not session:
        return None
    # Update last_seen
    session.last_seen_at = now
    await db.commit()
    user_result = await db.execute(
        select(User).where(User.id == session.user_id).where(User.is_active == True)
    )
    return user_result.scalar_one_or_none()


async def revoke_session(db: AsyncSession, token: str) -> None:
    """Deletes the session record for the given token."""
    token_hash = _hash_token(token)
    result = await db.execute(
        select(AuthSession).where(AuthSession.token_hash == token_hash)
    )
    session = result.scalar_one_or_none()
    if session:
        await db.delete(session)
        await db.commit()


async def register_student(
    db: AsyncSession, email: str, name: str, password: str
) -> User:
    """Creates a new student account. Raises ValueError on duplicate email."""
    existing = await db.execute(select(User).where(User.email == email.lower()))
    if existing.scalar_one_or_none():
        raise ValueError("An account with that email already exists.")
    user = User(
        email=email.lower(),
        name=name,
        hashed_password=hash_password(password),
        role=UserRole.student,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(
    db: AsyncSession, email: str, password: str
) -> Optional[User]:
    """Returns the user if credentials are valid and account is active."""
    result = await db.execute(select(User).where(User.email == email.lower()))
    user: Optional[User] = result.scalar_one_or_none()
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user
