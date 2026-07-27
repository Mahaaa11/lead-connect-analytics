"""Application login — password hashing and verification."""

from __future__ import annotations

import hashlib
import os
import secrets

PBKDF2_ITERATIONS = 260_000


def default_credentials() -> tuple[str, str]:
    username = os.environ.get("APP_DEFAULT_USER", "admin").strip() or "admin"
    password = os.environ.get("APP_DEFAULT_PASSWORD", "leadconnect")
    return username, password


def hash_password(password: str, *, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algo, iterations_raw, salt, digest_hex = stored_hash.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        iterations = int(iterations_raw)
        expected = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations,
        ).hex()
        return secrets.compare_digest(expected, digest_hex)
    except (ValueError, TypeError):
        return False
