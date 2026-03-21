"""Encryption utilities for the variable/secret store."""

import base64
import os

from cryptography.fernet import Fernet

from app.core.config import get_settings

settings = get_settings()


def _get_fernet() -> Fernet:
    key = settings.ENCRYPTION_KEY
    if not key:
        # Derive a deterministic key from SECRET_KEY for development convenience.
        raw = settings.SECRET_KEY.encode()
        key = base64.urlsafe_b64encode(raw.ljust(32, b"\0")[:32]).decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_value(plaintext: str) -> str:
    """Encrypt a string and return a base64 token."""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_value(token: str) -> str:
    """Decrypt a Fernet token back to plaintext."""
    return _get_fernet().decrypt(token.encode()).decode()


def generate_api_key() -> str:
    """Generate a random API key."""
    return base64.urlsafe_b64encode(os.urandom(32)).decode()
