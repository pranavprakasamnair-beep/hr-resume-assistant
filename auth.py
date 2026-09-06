"""
Password hashing helpers for recruiter (employee) authentication.

We NEVER store plaintext passwords. Each password gets a random per-user
salt, then is run through PBKDF2-HMAC-SHA256 with a high iteration count.
This is stdlib-only (hashlib), so no extra dependency is needed.

Used by:
  - generate_data.py / migrate_add_employees.py (to create employee accounts)
  - app.py (to verify a login attempt)
"""

import hashlib
import os
import hmac

ITERATIONS = 200_000


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """Returns (hash_hex, salt_hex). Generates a new random salt if none given."""
    if salt is None:
        salt_bytes = os.urandom(16)
        salt = salt_bytes.hex()
    else:
        salt_bytes = bytes.fromhex(salt)

    hash_bytes = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt_bytes, ITERATIONS
    )
    return hash_bytes.hex(), salt


def verify_password(password: str, salt_hex: str, expected_hash_hex: str) -> bool:
    """Recomputes the hash with the stored salt and compares safely."""
    computed_hash, _ = hash_password(password, salt_hex)
    return hmac.compare_digest(computed_hash, expected_hash_hex)
