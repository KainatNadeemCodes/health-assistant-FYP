"""
FILE: src/security.py
PURPOSE: Security utilities for JWT authentication, salted password hashing, and RBAC guards.
"""

import os
import secrets
import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Optional
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

# Secret keys and configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "health-assistant-secret-key-change-in-production-2025")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))  # 24 hours
ADMIN_SECRET = os.getenv("ADMIN_SECRET", "admin2025")

# Bearer token extractor
security_bearer = HTTPBearer(auto_error=False)


def hash_password(plain_text: str) -> str:
    """
    Cryptographically secure salted PBKDF2-HMAC-SHA256 password hashing.
    Replaces vulnerable unsalted SHA-256.
    """
    salt = secrets.token_hex(16)
    iterations = 100_000
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        plain_text.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    ).hex()
    return f"pbkdf2_sha256${salt}${derived}"


def verify_password(plain_text: str, stored_hash: str) -> bool:
    """
    Verifies a password against the stored hash.
    Supports PBKDF2-HMAC-SHA256 with backwards compatibility for legacy unsalted SHA-256.
    """
    if not stored_hash:
        return False

    if stored_hash.startswith("pbkdf2_sha256$"):
        parts = stored_hash.split("$")
        if len(parts) != 3:
            return False
        _, salt, expected_hash = parts
        derived = hashlib.pbkdf2_hmac(
            "sha256",
            plain_text.encode("utf-8"),
            salt.encode("utf-8"),
            100_000,
        ).hex()
        return hmac.compare_digest(derived, expected_hash)

    # Legacy fallback: plain unsalted SHA-256
    legacy_hash = hashlib.sha256(plain_text.encode("utf-8")).hexdigest()
    return hmac.compare_digest(legacy_hash, stored_hash)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Creates a signed JWT access token containing claims and an expiration time.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    return jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """
    Decodes and validates a JWT access token.
    Raises HTTPException 401 if invalid or expired.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
) -> Optional[dict]:
    """
    Extracts the user from Authorization: Bearer <token> if present, else returns None.
    Used for endpoints that support both authenticated users and guests (e.g. /predict).
    """
    if not credentials or not credentials.credentials:
        return None
    try:
        payload = decode_access_token(credentials.credentials)
        return payload
    except HTTPException:
        return None


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
) -> dict:
    """
    Strict dependency: Requires a valid Authorization: Bearer <token> header.
    Prevents IDOR by identifying the authenticated user from the cryptographically verified token.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decode_access_token(credentials.credentials)


async def get_current_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
) -> dict:
    """
    Strict dependency: Verifies that the authenticated caller has the 'admin' role.
    """
    user = await get_current_user(credentials)
    role = str(user.get("role", "")).lower()
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required to access this resource.",
        )
    return user
