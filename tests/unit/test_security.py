"""Unit tests for password hashing and JWT helpers."""

import pytest

from app.core.exceptions import UnauthorizedError
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_hash_password_is_not_plaintext():
    hashed = hash_password("supersecret1")
    assert hashed != "supersecret1"


def test_verify_password_roundtrip():
    hashed = hash_password("supersecret1")
    assert verify_password("supersecret1", hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_access_token_roundtrip():
    token = create_access_token(subject="user-123")
    assert decode_access_token(token) == "user-123"


def test_decode_invalid_token_raises():
    with pytest.raises(UnauthorizedError):
        decode_access_token("not-a-real-token")


def test_expired_token_raises():
    token = create_access_token(subject="user-123", expires_minutes=-1)
    with pytest.raises(UnauthorizedError):
        decode_access_token(token)
