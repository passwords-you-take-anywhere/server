from collections.abc import Generator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader
from sqlmodel import Session, select

from core.db import get_session
from core.models import Session as UserSession
from core.models import User
from core.settings import Settings

# Security scheme for Swagger UI
api_key_header = APIKeyHeader(name="X-Session-Id", auto_error=False)


def _get_settings() -> Settings:
    return Settings()


def get_db_session(settings: Settings = Depends(_get_settings)) -> Generator[Session]:
    """Get database session - can be overridden in tests."""
    with get_session(settings) as session:
        yield session


async def get_current_user(
    request: Request,
    db: Session = Depends(get_db_session),
    _api_key: str = Depends(api_key_header),
) -> User:
    """Get current authenticated user from session_id (UUIDv4 token)."""
    session_id = request.cookies.get("session_id") or request.headers.get("X-Session-Id")

    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    session = db.exec(select(UserSession).where(UserSession.id == session_id)).first()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )

    user = db.exec(select(User).where(User.id == session.user_id)).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user
