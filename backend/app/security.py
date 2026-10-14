"""Password hashing and short-lived bearer tokens. No credentials in browser storage."""
import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt
from jwt.exceptions import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .database import User, get_db

ALGORITHM = "HS256"
ITERATIONS = 600_000
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return "pbkdf2_sha256$%s$%s$%s" % (
        ITERATIONS, base64.b64encode(salt).decode(), base64.b64encode(digest).decode()
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt, stored = encoded.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), base64.b64decode(salt), int(rounds)
        )
        return hmac.compare_digest(actual, base64.b64decode(stored))
    except (ValueError, TypeError):
        return False


def access_token(user: User) -> str:
    expiry = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_minutes)
    return jwt.encode(
        {"sub": user.id, "org": user.org_id, "exp": expiry, "type": "access"},
        settings.secret_key, algorithm=ALGORITHM
    )


async def current_user(
    token: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    unauthenticated = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"}
    )
    if not token or token.scheme.lower() != "bearer":
        raise unauthenticated
    try:
        payload = jwt.decode(token.credentials, settings.secret_key, algorithms=[ALGORITHM])
        if payload.get("type") != "access" or not payload.get("sub"):
            raise unauthenticated
    except InvalidTokenError:
        raise unauthenticated
    user = await db.scalar(select(User).where(User.id == payload["sub"]))
    if user is None or user.org_id != payload.get("org"):
        raise unauthenticated
    return user
