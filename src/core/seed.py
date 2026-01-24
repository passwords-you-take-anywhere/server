from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlmodel import Session, select

from core.db import get_engine
from core.models import Auth, Domain, Storage, StorageDomain, User
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

        # Each storage entry will have multiple domains
        domains_per_storage = [
            ["example.com", "www.example.com"],
            ["mail.example.com", "smtp.example.com"],
            ["github.com", "gist.github.com", "api.github.com"],
            ["bank.example", "secure.bank.example"],
            ["forum.example", "api.forum.example"],
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

            for offset, domain_list in enumerate(domains_per_storage, start=1):
                storage_id = str(uuid4())
                storage = Storage(
                    id=storage_id,
                    user_id=user.id,
                    username_data=f"{email.split('@')[0]}_{offset}".encode("ascii"),
                    password_data=f"{password}_site{offset}".encode("ascii"),
                    created_at=datetime.now(UTC) - timedelta(days=offset),
                    notes=f"seeded record {offset} for {email}".encode("ascii"),
                    updated=datetime.now(UTC) - timedelta(days=offset),
                )
                db.add(storage)

                # Create domain records for each domain in the list
                for _domain_idx, domain_str in enumerate(domain_list):
                    domain = Domain(
                        id=str(uuid4()),
                        encrypted_domain=domain_str.encode("ascii"),
                    )
                    db.add(domain)

                    storage_domain = StorageDomain(
                        id=str(uuid4()),
                        storage_id=storage_id,
                        domain_id=domain.id,
                    )
                    db.add(storage_domain)

        db.commit()
        return True
