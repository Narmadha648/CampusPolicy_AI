"""FastAPI dependency helpers for authentication and authorization."""
from typing import Optional

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User, UserRole
from app.services.auth_service import SESSION_COOKIE, get_user_from_token


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    cp_session: Optional[str] = Cookie(default=None),
) -> User:
    """Returns the authenticated user or raises 401."""
    if not cp_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    user = await get_user_from_token(db, cp_session)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or invalid",
        )
    return user


async def require_student(user: User = Depends(get_current_user)) -> User:
    if user.role not in (UserRole.student, UserRole.admin):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user
