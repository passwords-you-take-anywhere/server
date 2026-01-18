from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlmodel import Session, select

from core.db import get_engine
from core.models import Auth, Storage, User
from core.passwords import hash_password
from core.settings import Settings


def seed_if_empty(settings: Settings) -> bool:
    engine = get_engine(settings)
    with Session(engine) as db:
        existing = db.exec(select(Auth).limit(1)).first()
        if existing:
            return False

        users = [
            ("alice@example.com", "Alice!234"),
            ("bob@example.com", "Bob!2345"),
            ("carol@example.com", "Carol!23"),
        ]

        domains = [
            "example.com",
            "mail.example.com",
            "github.com",
            "bank.example",
            "forum.example",
        ]

        for index, (email, password) in enumerate(users, start=1):
            auth = Auth(
                id=str(uuid4()),
                role_id="user",
                email=email,
                password=hash_password(password),
            )
            user = User(
                id=str(uuid4()),
                auth_id=auth.id,
                encryption_key=(f"key-{index:02d}-" + "x" * 24).encode("ascii"),
            )
            db.add(auth)
            db.add(user)

            for offset, domain in enumerate(domains, start=1):
                storage = Storage(
                    id=str(uuid4()),
                    user_id=user.id,
                    username_data=f"{email.split('@')[0]}_{offset}".encode("ascii"),
                    password_data=f"{password}_site{offset}".encode("ascii"),
                    domains=domain.encode("ascii"),
                    notes=f"seeded record {offset} for {email}".encode("ascii"),
                    updated=datetime.now(UTC) - timedelta(days=offset),
                )
                db.add(storage)

        db.commit()
        return True
