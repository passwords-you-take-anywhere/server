from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from urllib.parse import quote_plus

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine
from src.core.settings import Settings


def build_database_url(settings: Settings) -> str:
    user = quote_plus(settings.db_user)
    password = quote_plus(settings.db_password)
    host = settings.db_host
    port = settings.db_port
    db = quote_plus(settings.db_name)
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}?connect_timeout=3"


@lru_cache(maxsize=8)
def _get_engine(database_url: str, *, echo: bool) -> Engine:
    return create_engine(database_url, echo=echo, pool_pre_ping=True)


def get_engine(settings: Settings) -> Engine:
    return _get_engine(build_database_url(settings), echo=settings.debug)


@contextmanager
def get_session(settings: Settings) -> Iterator[Session]:
    engine = get_engine(settings)
    with Session(engine) as session:
        yield session


def init_db(settings: Settings) -> None:
    # Ensure models are imported so they register with SQLModel.metadata
    from src.core import models as _models  # noqa: F401  # pyright: ignore[reportUnusedImport]

    engine = get_engine(settings)
    SQLModel.metadata.create_all(engine)
