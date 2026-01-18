from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr
from sqlmodel import select

from core.db import get_session
from core.models import Auth, User
from core.models import Session as UserSession
from core.passwords import hmac_hash
from core.settings import Settings


class MeResponse(BaseModel):
    email: EmailStr
    avatar: str

me_router = APIRouter(prefix="")

def _get_settings() -> Settings:
    return Settings()

@me_router.get("/me", response_model=MeResponse)
async def me(
    request: Request,
    settings: Settings = Depends(_get_settings),  # noqa
):
    session_id = request.cookies.get("session_id") or request.headers.get("X-Session-Id")

    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    with get_session(settings) as db:
        session = db.exec(
            select(UserSession).where(UserSession.id == session_id)
        ).first()

        if not session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid session",
            )

        user = db.exec(
            select(User).where(User.id == session.user_id)
        ).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

        auth = db.exec(
            select(Auth).where(Auth.id == user.auth_id)
        ).first()

        if not auth:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Auth record missing",
            )
        email_hash = hmac_hash(
            value=auth.email,
            key=user.encryption_key,
        )
        url = f"https://api.dicebear.com/9.x/glass/svg?seed={email_hash}"

        return MeResponse(email=auth.email, avatar=url)

