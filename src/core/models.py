# ruff: noqa: UP006, UP035, UP045, UP037

from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, LargeBinary, func
from sqlalchemy.schema import Column
from sqlmodel import Field, Relationship, SQLModel  # pyright: ignore[reportUnknownVariableType]


class Auth(SQLModel, table=True):
    id: str = Field(primary_key=True)
    role_id: str = Field(nullable=False)
    email: str = Field(nullable=False, unique=True, index=True)
    password: str = Field(nullable=False)

    user: Optional["User"] = Relationship(back_populates="auth")


class User(SQLModel, table=True):
    __table_args__ = {"quote": True}

    id: str = Field(primary_key=True)
    auth_id: str = Field(foreign_key="auth.id", nullable=False, unique=True, index=True)
    encryption_key: bytes = Field(sa_column=Column(LargeBinary, nullable=False))

    auth: Optional[Auth] = Relationship(back_populates="user")

    storages: List["Storage"] = Relationship(back_populates="user")
    sessions: List["Session"] = Relationship(back_populates="user")


class Session(SQLModel, table=True):
    id: str = Field(primary_key=True, index=True)
    user_id: str = Field(foreign_key="user.id", nullable=False, index=True)

    user: Optional["User"] = Relationship(back_populates="sessions")


class Domain(SQLModel, table=True):
    id: str = Field(primary_key=True)
    encrypted_domain: bytes = Field(sa_column=Column(LargeBinary, nullable=False))

    storage_domains: List["StorageDomain"] = Relationship(back_populates="domain")


class StorageDomain(SQLModel, table=True):
    id: str = Field(primary_key=True)
    storage_id: str = Field(foreign_key="storage.id", nullable=False, index=True)
    domain_id: str = Field(foreign_key="domain.id", nullable=False, index=True)

    storage: Optional["Storage"] = Relationship(back_populates="storage_domains")
    domain: Optional[Domain] = Relationship(back_populates="storage_domains")


class Storage(SQLModel, table=True):
    id: str = Field(primary_key=True)
    user_id: str = Field(foreign_key="user.id", nullable=False, index=True)

    username_data: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    password_data: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    notes: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    created_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now()),
    )
    updated: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, index=True),
    )
    deleted_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True, index=True),
    )

    user: Optional[User] = Relationship(back_populates="storages")
    storage_domains: List[StorageDomain] = Relationship(back_populates="storage")
