import base64
import hashlib
import hmac

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

# hash using user-specific key
def hmac_hash(value: str, key: bytes) -> str:
    digest = hmac.new(
        key=key,
        msg=value.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).digest()

    return base64.urlsafe_b64encode(digest).decode("ascii")

