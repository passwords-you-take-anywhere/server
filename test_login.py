#!/usr/bin/env python3
"""Test login by simulating frontend's hashing process"""
import json
import urllib.request

from argon2.low_level import Type, hash_secret_raw


def create_high_entropy_hash(password: str, salt: str) -> str:
    """Simulates frontend's argon2id with exact parameters"""
    hash_bytes = hash_secret_raw(
        secret=password.encode("utf-8"),
        salt=salt.encode("utf-8"),
        time_cost=1,  # iterations
        memory_cost=512,  # 512KB memory
        parallelism=1,
        hash_len=32,  # 32 bytes output
        type=Type.ID  # argon2id
    )
    return hash_bytes.hex()


def create_master_key(master_password: str, email: str) -> str:
    """Simulates frontend's createMasterKey"""
    salt = email.lower().strip()
    return create_high_entropy_hash(master_password, salt)


def create_auth_key(master_key: str, master_password: str) -> str:
    """Simulates frontend's createAuthKey"""
    return create_high_entropy_hash(master_password, master_key)


def test_login(email: str, password: str):
    """Test login with given credentials"""
    print(f"\n=== Testing login for {email} ===")

    # Step 1: Create master key
    master_key = create_master_key(password, email)
    print(f"Master Key: {master_key[:20]}...")

    # Step 2: Create auth key
    auth_key = create_auth_key(master_key, password)
    print(f"Auth Key: {auth_key[:20]}...")

    # Step 3: Send login request
    data = json.dumps({
        "email": email,
        "password": auth_key
    }).encode("utf-8")

    req = urllib.request.Request(
        "http://localhost:8000/auth/login",
        data=data,
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))
            print("✓ Login successful!")
            print(f"Session ID: {result['session_id']}")
            return True
    except urllib.error.HTTPError as e:
        error_msg = e.read().decode("utf-8")
        print(f"✗ Login failed: {e.code}")
        print(f"Error: {error_msg}")
        return False


if __name__ == "__main__":
    # Test with seeded users
    users = [
        ("alice@example.com", "Alice!234"),
        ("bob@example.com", "Bob!2345"),
        ("carol@example.com", "Carol!23"),
    ]

    for email, password in users:
        test_login(email, password)
