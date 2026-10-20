"""One-time account recovery/verification and revocable sessions."""
import asyncio
import hashlib
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .database import AccountToken, User, get_db
from .rate_limit import throttle
from .security import current_user, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["accounts"])


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def aware(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def create_one_time_token(db: AsyncSession, user: User, purpose: str) -> str:
    if purpose not in {"verify_email", "reset_password"}:
        raise ValueError("Unsupported purpose")
    secret = secrets.token_urlsafe(48)
    db.add(AccountToken(
        user_id=user.id,
        token_hash=hashlib.sha256(secret.encode()).hexdigest(),
        purpose=purpose,
        expires_at=utc_now() + timedelta(hours=24 if purpose == "verify_email" else 1)
    ))
    return secret


def _send_smtp(recipient: str, subject: str, body: str) -> None:
    email = EmailMessage()
    email["From"] = settings.smtp_sender
    email["To"] = recipient
    email["Subject"] = subject
    email.set_content(body)
    context = ssl.create_default_context()
    if settings.smtp_port == 465:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15, context=context) as server:
            server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(email)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as server:
            server.starttls(context=context)
            server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(email)


async def deliver_email(recipient: str, purpose: str, secret: str) -> None:
    if not settings.smtp_host or not settings.smtp_sender:
        raise HTTPException(503, "Account email delivery is not configured")
    path = "/#verify=" if purpose == "verify_email" else "/#reset="
    link = settings.app_public_url.rstrip("/") + path + quote(secret)
    subject = "Verify your RegTech account" if purpose == "verify_email" else "Reset your RegTech password"
    expiration = "24 hours" if purpose == "verify_email" else "one hour"
    body = (
        "Use this one-time link within " + expiration + ":\n\n" + link
        + "\n\nIf you did not request this, ignore this message."
    )
    try:
        await asyncio.to_thread(_send_smtp, recipient, subject, body)
    except Exception as error:
        raise HTTPException(503, "Email delivery temporarily unavailable") from error


class EmailRequest(BaseModel):
    email: EmailStr


class ResetPassword(BaseModel):
    token: str = Field(min_length=30, max_length=256)
    new_password: str = Field(min_length=12, max_length=128)


class VerifyEmail(BaseModel):
    token: str = Field(min_length=30, max_length=256)


class ChangePassword(BaseModel):
    current_password: str
    new_password: str = Field(min_length=12, max_length=128)


async def redeem(db: AsyncSession, secret: str, purpose: str) -> tuple[User, AccountToken]:
    hashed = hashlib.sha256(secret.encode()).hexdigest()
    record = await db.scalar(
        select(AccountToken).where(
            AccountToken.token_hash == hashed, AccountToken.purpose == purpose
        ).with_for_update()
    )
    if not record or record.consumed_at is not None or aware(record.expires_at) <= utc_now():
        raise HTTPException(400, "Invalid or expired link")
    user = await db.scalar(select(User).where(User.id == record.user_id).with_for_update())
    if user is None:
        raise HTTPException(400, "Invalid or expired link")
    record.consumed_at = utc_now()
    return user, record


@router.post("/request-password-reset", status_code=202)
async def request_password_reset(
    payload: EmailRequest, request: Request, db: AsyncSession = Depends(get_db)
):
    throttle(request, "password_email")
    user = await db.scalar(select(User).where(User.email == str(payload.email).lower()))
    if user:
        secret = create_one_time_token(db, user, "reset_password")
        await db.commit()
        await deliver_email(user.email, "reset_password", secret)
    return {"detail": "If an account exists, a reset link will be sent."}


@router.post("/reset-password")
async def reset_password(payload: ResetPassword, db: AsyncSession = Depends(get_db)):
    user, record = await redeem(db, payload.token, "reset_password")
    user.password_hash = hash_password(payload.new_password)
    user.session_version += 1
    await db.execute(
        update(AccountToken).where(
            AccountToken.user_id == user.id, AccountToken.consumed_at.is_(None)
        ).values(consumed_at=utc_now())
    )
    user.failed_attempts = 0
    user.locked_until = None
    await db.commit()
    return {"detail": "Password updated. Sign in again on all devices."}


@router.post("/verify-email")
async def verify_email(payload: VerifyEmail, db: AsyncSession = Depends(get_db)):
    user, record = await redeem(db, payload.token, "verify_email")
    if user.verified_at is not None:
        raise HTTPException(400, "Invalid or expired link")
    user.verified_at = utc_now()
    user.session_version += 1
    await db.execute(
        update(AccountToken).where(
            AccountToken.user_id == user.id, AccountToken.purpose == "verify_email",
            AccountToken.consumed_at.is_(None)
        ).values(consumed_at=utc_now())
    )
    await db.commit()
    return {"detail": "Email verified. You can sign in."}


@router.post("/resend-verification", status_code=202)
async def resend_verification(
    payload: EmailRequest, request: Request, db: AsyncSession = Depends(get_db)
):
    throttle(request, "password_email")
    user = await db.scalar(select(User).where(User.email == str(payload.email).lower()))
    if user and user.verified_at is None:
        secret = create_one_time_token(db, user, "verify_email")
        await db.commit()
        await deliver_email(user.email, "verify_email", secret)
    return {"detail": "If verification is required, a link will be sent."}


@router.post("/change-password")
async def change_password(
    payload: ChangePassword, user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db)
):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    user.password_hash = hash_password(payload.new_password)
    user.session_version += 1
    await db.execute(
        update(AccountToken).where(
            AccountToken.user_id == user.id, AccountToken.consumed_at.is_(None)
        ).values(consumed_at=utc_now())
    )
    user.failed_attempts = 0
    user.locked_until = None
    await db.commit()
    return {"detail": "Password changed. All existing access tokens are revoked."}


@router.post("/logout")
async def logout(user: User = Depends(current_user), db: AsyncSession = Depends(get_db)):
    user.session_version += 1
    await db.commit()
    return {"detail": "Signed out from all sessions."}
