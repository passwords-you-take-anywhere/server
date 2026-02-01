#!/usr/bin/env python3
"""Verify seed data and test authentication flow"""
import sys

sys.path.insert(0, "/home/memetelve/pyta/server/src")

from hashlib import pbkdf2_hmac

import psycopg

from core.passwords import verify_password


def create_high_entropy_hash(password: str, salt: str) -> str:
    """Simulates frontend's argon2id using PBKDF2"""
    hash_bytes = pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100000,
        dklen=32
    )
    return hash_bytes.hex()


def create_master_key(master_password: str, email: str) -> str:
    salt = email.lower().strip()
    return create_high_entropy_hash(master_password, salt)


def create_auth_key(master_key: str, master_password: str) -> str:
    return create_high_entropy_hash(master_password, master_key)


# Connect to database
conn = psycopg.connect(
    "postgresql://user:pass@localhost:5432/pyta"
)

cursor = conn.cursor()
cursor.execute("SELECT email, password FROM auth WHERE email = 'alice@example.com'")
row = cursor.fetchone()

if row:
    email, stored_hash = row
    print(f"Email: {email}")
    print(f"Stored hash: {stored_hash[:50]}...")

    # Test with plain password
    plain_password = "Alice!234"
    print(f"\n1. Testing with plain password: {plain_password}")
    print(f"   Result: {verify_password(plain_password, stored_hash)}")

    # Test with auth key
    master_key = create_master_key(plain_password, email)
    auth_key = create_auth_key(master_key, plain_password)
    print("\n2. Testing with auth key (frontend simulation):")
    print(f"   Master Key: {master_key[:30]}...")
    print(f"   Auth Key: {auth_key[:30]}...")
    print(f"   Result: {verify_password(auth_key, stored_hash)}")

conn.close()
