from __future__ import annotations

from src.auth.hashing import hash_api_key, verify_api_key
from src.auth.key_service import APIKeyService
from src.core.exceptions import AuthenticationError


def test_hash_and_verify_api_key() -> None:
    raw_key = "gk_testprefix_secret-value"
    key_hash = hash_api_key(raw_key)
    assert verify_api_key(raw_key, key_hash) is True
    assert verify_api_key("gk_testprefix_other", key_hash) is False


def test_api_key_parse_rejects_invalid_format() -> None:
    try:
        APIKeyService.parse_presented_key("invalid")
    except AuthenticationError:
        assert True
    else:
        raise AssertionError("invalid API key format should raise AuthenticationError")
