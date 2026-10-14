"""Authentication endpoints: register, login, logout, me."""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.schemas.auth import AuthResponse, LoginRequest, RegisterRequest, UserOut
from app.services.auth_service import (
    SESSION_COOKIE,
    authenticate_user,
    create_session,
    register_student,
    revoke_session,
)
from app.services.deps import get_current_user
from app.models.user import User

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter()

_COOKIE_OPTS = dict(
    key=SESSION_COOKIE,
    httponly=True,
    secure=settings.cookie_secure,
    samesite=settings.cookie_samesite,
    max_age=settings.session_expire_days * 86400,
    path="/",
)


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Register a new student account. Public endpoint."""
    try:
        user = await register_student(db, body.email, body.name, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    token = await create_session(
        db,
        user,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    response.set_cookie(value=token, **_COOKIE_OPTS)
    logger.info("New student registered: %s", user.email)
    return AuthResponse(user=UserOut.model_validate(user), message="Registration successful")


@router.post("/login", response_model=AuthResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate and set session cookie."""
    user = await authenticate_user(db, body.email, body.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    token = await create_session(
        db,
        user,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    response.set_cookie(value=token, **_COOKIE_OPTS)
    logger.info("User logged in: %s", user.email)
    return AuthResponse(user=UserOut.model_validate(user), message="Login successful")


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    response: Response,
    db: AsyncSession = Depends(get_db),
    cp_session: Optional[str] = None,
    request: Request = None,
):
    """Revoke the current session and clear the cookie."""
    from fastapi import Cookie
    # Read cookie directly from request to avoid optional-dependency typing issues
    token = request.cookies.get(SESSION_COOKIE) if request else None
    if token:
        await revoke_session(db, token)
    response.delete_cookie(key=SESSION_COOKIE, path="/")
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    """Return the currently authenticated user."""
    return UserOut.model_validate(user)
