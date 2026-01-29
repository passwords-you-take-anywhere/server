from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4
from secrets import token_bytes
import json
import base64

from argon2 import PasswordHasher
from argon2.low_level import hash_secret_raw, Type
from jwcrypto import jwe, jwk

from sqlmodel import Session, select

from core.db import get_engine
from core.models import Auth, Domain, Storage, StorageDomain, User
from core.passwords import hash_password
from core.settings import Settings


def create_high_entropy_hash(password: str, salt: str) -> str:
    """
    Replicates frontend's argon2id hashing with exact same parameters:
    - parallelism: 1
    - iterations: 1
    - memorySize: 512KB
    - hashLength: 32 bytes
    """
    hash_bytes = hash_secret_raw(
        secret=password.encode('utf-8'),
        salt=salt.encode('utf-8'),
        time_cost=1,  # iterations
        memory_cost=512,  # 512KB memory
        parallelism=1,
        hash_len=32,  # 32 bytes output
        type=Type.ID  # argon2id
    )
    return hash_bytes.hex()


def create_master_key(master_password: str, email: str) -> str:
    """Replicates frontend's createMasterKey"""
    salt = email.lower().strip()
    return create_high_entropy_hash(master_password, salt)


def create_auth_key(master_key: str, master_password: str) -> str:
    """Replicates frontend's createAuthKey"""
    return create_high_entropy_hash(master_password, master_key)


def generate_vault_key() -> bytes:
    """Generates a 256-bit (32-byte) symmetric key using CSPRNG"""
    return token_bytes(32)


def encrypt_vault_key(vault_key: bytes, master_key: str) -> str:
    """
    Encrypts the vault key using master key with A256GCM (JWE)
    Replicates frontend's encryptVaultKey function
    """
    # Generate 128-bit (16-byte) IV
    iv = token_bytes(16)
    
    combined = vault_key + iv
    
    master_key_bytes = master_key.encode('utf-8')[:32]
    
    master_key_b64 = base64.urlsafe_b64encode(master_key_bytes).decode('utf-8').rstrip('=')
    
    key = jwk.JWK(kty="oct", k=master_key_b64)
    
    jwe_token = jwe.JWE(
        plaintext=combined,
        protected=json.dumps({"alg": "dir", "enc": "A256GCM"})
    )
    jwe_token.add_recipient(key)
    
    return jwe_token.serialize(compact=True)


def encrypt_vault_string(data: str, vault_key: bytes) -> str:
    """
    Encrypts a string using the vault key with A256GCM (JWE)
    Replicates frontend's encryptVaultString function
    """
    # Base64url encode the vault key for JWK
    vault_key_b64 = base64.urlsafe_b64encode(vault_key).decode('utf-8').rstrip('=')
    
    # Create JWK from vault key
    key = jwk.JWK(kty="oct", k=vault_key_b64)
    
    # Create JWE with dir (direct key agreement) and A256GCM
    jwe_token = jwe.JWE(
        plaintext=data.encode('utf-8'),
        protected=json.dumps({"alg": "dir", "enc": "A256GCM"})
    )
    jwe_token.add_recipient(key)
    
    return jwe_token.serialize(compact=True)


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
            master_key = create_master_key(password, email)
            auth_key = create_auth_key(master_key, password)
            vault_key = generate_vault_key()
            encrypted_vault_key = encrypt_vault_key(vault_key, master_key)
            
            auth = Auth(
                id=str(uuid4()),
                role_id="user",
                email=email,
                password=hash_password(auth_key),  # Hash the auth_key, not the plain password
            )
            user = User(
                id=str(uuid4()),
                auth_id=auth.id,
                encryption_key=encrypted_vault_key.encode("utf-8"),  # Store encrypted vault key
            )
            db.add(auth)
            db.add(user)

            for offset, domain_list in enumerate(domains_per_storage, start=1):
                storage_id = str(uuid4())
                
                # Encrypt storage data with vault key
                username = f"{email.split('@')[0]}_{offset}"
                password_value = f"{password}_site{offset}"
                notes = f"seeded record {offset} for {email}"
                
                storage = Storage(
                    id=storage_id,
                    user_id=user.id,
                    username_data=encrypt_vault_string(username, vault_key).encode("utf-8"),
                    password_data=encrypt_vault_string(password_value, vault_key).encode("utf-8"),
                    created_at=datetime.now(UTC) - timedelta(days=offset),
                    notes=encrypt_vault_string(notes, vault_key).encode("utf-8"),
                    updated=datetime.now(UTC) - timedelta(days=offset),
                )
                db.add(storage)

                # Create domain records for each domain in the list
                for _domain_idx, domain_str in enumerate(domain_list):
                    domain = Domain(
                        id=str(uuid4()),
                        encrypted_domain=encrypt_vault_string(domain_str, vault_key).encode("utf-8"),
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
