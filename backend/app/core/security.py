"""Security primitives: password hashing, OTP hashing, session tokens.

Uses only the Python standard library (PBKDF2-HMAC-SHA256) so the project
stays dependency-light and zero-cost.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000)
    return f"pbkdf2_sha256$200000${salt}${dk.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        algo, iterations, salt, expected = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), int(iterations)
        )
        return hmac.compare_digest(dk.hex(), expected)
    except Exception:
        return False


def hash_otp(otp: str) -> str:
    """Salted SHA-256 hash of a short OTP (short codes cannot be peppered
    with per-row salt without storing it, so a global salt is used)."""
    salt = "careerdna-otp-salt-v1"
    return hashlib.sha256(f"{salt}:{otp}".encode()).hexdigest()


def verify_otp(otp: str, stored_hash: str | None) -> bool:
    if not stored_hash or not otp:
        return False
    return hmac.compare_digest(hash_otp(otp.strip()), stored_hash)


def generate_otp() -> str:
    return "".join(secrets.choice("0123456789") for _ in range(6))


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def mask_email(email: str) -> str:
    """d***a@northfielddemo.edu style masking."""
    if not email or "@" not in email:
        return "•••@•••"
    local, domain = email.split("@", 1)
    if len(local) <= 2:
        masked = local[0] + "*" * max(len(local) - 1, 1)
    else:
        masked = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked}@{domain}"


def utcnow() -> datetime:
    """Naive UTC timestamp.

    SQLite stores naive datetimes; using naive UTC everywhere (writes and
    comparisons) keeps comparisons valid and consistent across the app.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def naive_utc(dt: datetime | None) -> datetime | None:
    """Normalize a datetime read from the DB (may carry an offset) to
    naive UTC so it can be compared with utcnow()."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def session_expiry() -> datetime:
    from app.core.config import get_settings

    return utcnow() + timedelta(hours=get_settings().session_max_age_hours)
