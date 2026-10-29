from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

_PASSWORD_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=64 * 1024,
    parallelism=4,
    hash_len=32,
)


def hash_api_key(raw_key: str) -> str:
    return _PASSWORD_HASHER.hash(raw_key)


def verify_api_key(raw_key: str, key_hash: str) -> bool:
    try:
        return _PASSWORD_HASHER.verify(key_hash, raw_key)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
