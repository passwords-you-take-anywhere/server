from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr
from sqlmodel import select

from core.db import get_session
from core.models import Auth, User
from core.models import Session as UserSession
from core.passwords import verify_password
from core.settings import Settings


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    session_id: str

def _get_settings() -> Settings:
    return Settings()

auth_router = APIRouter(prefix="/auth", tags=["auth"])



@auth_router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    response: Response,
    settings: Settings = Depends(_get_settings),  # noqa
):
    with get_session(settings) as db:
        auth = db.exec(
            select(Auth).where(Auth.email == payload.email)
        ).first()

        if not auth or not verify_password(payload.password, auth.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        user = db.exec(
            select(User).where(User.auth_id == auth.id)
        ).first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User record missing in db",
            )

        session = UserSession(
            id=str(uuid4()),
            user_id=user.id,
        )

        db.add(session)
        db.commit()

        response.set_cookie(
            key="session_id",
            value=session.id,
            httponly=True,
            secure=not settings.debug,
            samesite="lax",
        )

        return LoginResponse(session_id=session.id)

@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    settings: Settings = Depends(_get_settings), # noqa
):
    session_id = request.cookies.get("session_id") or request.headers.get("X-Session-Id")

    if not session_id:
        response.delete_cookie("session_id")
        return

    with get_session(settings) as db:
        session = db.exec(
            select(UserSession).where(UserSession.id == session_id)
        ).first()

        if session:
            db.delete(session)
            db.commit()

    response.delete_cookie(
        key="session_id",
        httponly=True,
        secure=not settings.debug,
        samesite="lax",
    )
