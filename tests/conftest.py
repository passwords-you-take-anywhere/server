# Test configuration
import os
from collections.abc import Generator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncGenerator
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from core.db import get_session
from core.models import Auth, Session as UserSession
from core.models import Storage, User
from core.settings import Settings


@pytest.fixture(name="test_settings")
def test_settings_fixture() -> Settings:
    """Test settings with in-memory database."""
    return Settings(
        db_host="localhost",
        db_port=5432,
        db_user="test",
        db_password="test",
        db_name=":memory:",
    )


@pytest.fixture(name="engine")
def engine_fixture() -> Any:
    """Create in-memory SQLite engine for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(name="session")
def session_fixture(engine: Any) -> Generator[Session, None, None]:
    """Create a test database session."""
    with Session(engine) as session:
        yield session


@pytest.fixture(name="app")
def app_fixture(engine: Any) -> FastAPI:
    """Create FastAPI app with test configuration."""
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware
    from v1.auth.auth_router import auth_router
    from v1.auth.dependencies import get_db_session
    from v1.sync import sync_router

    # Create app without lifespan (no DB init during testing)
    @asynccontextmanager
    async def test_lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
        # Don't initialize real database in tests
        yield

    app = FastAPI(title="PYTA API Test", lifespan=test_lifespan)
    app.add_middleware(CORSMiddleware)
    app.include_router(auth_router)
    app.include_router(sync_router)

    # Override get_db_session to use test database
    def get_test_db_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_db_session] = get_test_db_session

    return app


@pytest.fixture(name="client")
def client_fixture(app: FastAPI) -> Generator[TestClient, None, None]:
    """Create test client."""
    with TestClient(app) as client:
        yield client


@pytest.fixture(name="test_user")
def test_user_fixture(session: Session) -> User:
    """Create a test user with auth."""
    auth = Auth(
        id=str(uuid4()),
        role_id="user",
        email="test@example.com",
        password="hashed_password",
    )
    session.add(auth)

    user = User(
        id=str(uuid4()),
        auth_id=auth.id,
        encryption_key=b"test_encryption_key",
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    return user


@pytest.fixture(name="test_session")
def test_session_fixture(session: Session, test_user: User) -> UserSession:
    """Create a test session for authentication."""
    user_session = UserSession(
        id=str(uuid4()),
        user_id=test_user.id,
    )
    session.add(user_session)
    session.commit()
    session.refresh(user_session)

    return user_session


@pytest.fixture(name="auth_headers")
def auth_headers_fixture(test_session: UserSession) -> dict[str, str]:
    """Create authentication headers with session token."""
    return {"X-Session-Id": test_session.id}


@pytest.fixture(name="test_storage_items")
def test_storage_items_fixture(session: Session, test_user: User) -> list[Storage]:
    """Create test storage items."""
    items = []
    base_time = datetime(2026, 1, 13, 10, 0, 0)

    for i in range(5):
        storage = Storage(
            id=str(uuid4()),
            user_id=test_user.id,
            username_data=f"encrypted_username_{i}".encode(),
            password_data=f"encrypted_password_{i}".encode(),
            domains=f"encrypted_domains_{i}".encode(),
            notes=f"encrypted_notes_{i}".encode(),
            created_at=base_time,
            updated=datetime(2026, 1, 13, 10, i, 0),
            deleted_at=None,
        )
        session.add(storage)
        items.append(storage)

    session.commit()

    for item in items:
        session.refresh(item)

    return items
