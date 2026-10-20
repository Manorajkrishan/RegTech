"""Tenant-safe invitations and team RBAC. Users belong to exactly one workspace."""
import asyncio
import hashlib
import secrets
from datetime import timedelta
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .account_actions import _send_smtp, utc_now, aware
from .config import settings
from .database import Organisation, TeamInvitation, User, get_db
from .rate_limit import throttle
from .security import current_user, hash_password, access_token

router = APIRouter(prefix="/api/team", tags=["team"])
ROLES = ("owner", "editor", "reviewer", "viewer")


def require_owner(user: User):
    if user.role != "owner":
        raise HTTPException(403, "Only the workspace owner can manage the team")


def can_write(user: User):
    if user.role not in ("owner", "editor"):
        raise HTTPException(403, "Editor or owner role required")


def can_review(user: User, creator_id: str):
    if user.role == "owner":
        return
    if user.role != "reviewer" or user.id == creator_id:
        raise HTTPException(403, "Independent reviewer or owner role required")


async def send_invite(email: str, organization: str, secret: str):
    if not settings.smtp_host or not settings.smtp_sender:
        raise HTTPException(503, "Invite email delivery is not configured")
    url = settings.app_public_url.rstrip("/") + "/#invite=" + quote(secret)
    body = (
        "You have been invited to the " + organization + " RegTech workspace.\n"
        "Use this one-time invitation link within seven days:\n\n" + url +
        "\n\nDo not forward this link. Ignore if unexpected."
    )
    try:
        await asyncio.to_thread(
            _send_smtp, email, "Invitation to RegTech — " + organization, body
        )
    except Exception as exc:
        raise HTTPException(503, "Invite email delivery failed") from exc


class InviteInput(BaseModel):
    email: EmailStr
    role: str = Field(pattern="^(editor|reviewer|viewer)$")


class AcceptInvite(BaseModel):
    token: str = Field(min_length=30, max_length=256)
    password: str = Field(min_length=12, max_length=128)


@router.get("")
async def team_roster(
    user: User = Depends(current_user), db: AsyncSession = Depends(get_db)
):
    members = (await db.scalars(
        select(User).where(User.org_id == user.org_id).order_by(User.created_at)
    )).all()
    pending = (await db.scalars(
        select(TeamInvitation).where(
            TeamInvitation.org_id == user.org_id,
            TeamInvitation.accepted_at.is_(None),
            TeamInvitation.revoked_at.is_(None),
            TeamInvitation.expires_at > utc_now(),
        ).order_by(TeamInvitation.created_at)
    )).all()
    return {
        "members": [
            {"id": m.id, "email": m.email, "role": m.role, "is_active": m.is_active}
            for m in members
        ],
        "pending": [
            {"id": m.id, "email": m.email, "role": m.role,
             "expires_at": m.expires_at.isoformat()}
            for m in pending
        ] if user.role == "owner" else []
    }


@router.post("/invitations", status_code=201)
async def invite(
    payload: InviteInput, request: Request, user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db)
):
    require_owner(user)
    throttle(request, "invite")
    email = str(payload.email).lower().strip()
    if await db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(409, "Email is already registered")
    if await db.scalar(select(TeamInvitation.id).where(
        TeamInvitation.org_id == user.org_id, TeamInvitation.email == email,
        TeamInvitation.accepted_at.is_(None), TeamInvitation.revoked_at.is_(None),
        TeamInvitation.expires_at > utc_now()
    )):
        raise HTTPException(409, "An invitation is already pending")
    org = await db.get(Organisation, user.org_id)
    if org.subscription_status not in ("active", "trialing"):
        members = await db.scalar(select(func.count(User.id)).where(
            User.org_id == user.org_id, User.is_active.is_(True)
        ))
        invites = await db.scalar(select(func.count(TeamInvitation.id)).where(
            TeamInvitation.org_id == user.org_id,
            TeamInvitation.accepted_at.is_(None),
            TeamInvitation.revoked_at.is_(None),
            TeamInvitation.expires_at > utc_now()
        ))
        if (members or 0) + (invites or 0) >= 3:
            raise HTTPException(402, "Free workspaces support up to three team seats")
    secret = secrets.token_urlsafe(48)
    invitation = TeamInvitation(
        org_id=user.org_id, email=email, role=payload.role,
        token_hash=hashlib.sha256(secret.encode()).hexdigest(),
        expires_at=utc_now() + timedelta(days=7), invited_by=user.id
    )
    db.add(invitation)
    await send_invite(email, org.name, secret)
    await db.commit()
    return {"id": invitation.id, "detail": "Invitation emailed"}


@router.post("/accept")
async def accept_invite(
    payload: AcceptInvite, request: Request, db: AsyncSession = Depends(get_db)
):
    throttle(request, "accept_invite")
    hashed = hashlib.sha256(payload.token.encode()).hexdigest()
    inv = await db.scalar(select(TeamInvitation).where(
        TeamInvitation.token_hash == hashed
    ).with_for_update())
    if not inv or inv.accepted_at or inv.revoked_at or aware(inv.expires_at) <= utc_now():
        raise HTTPException(400, "Invalid or expired invitation")
    if await db.scalar(select(User.id).where(User.email == inv.email)):
        raise HTTPException(409, "This email is already registered")
    user = User(
        org_id=inv.org_id, email=inv.email, role=inv.role,
        password_hash=hash_password(payload.password),
        verified_at=utc_now(), is_active=True
    )
    db.add(user)
    inv.accepted_at = utc_now()
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(409, "Invitation is no longer available") from exc
    return {"access_token": access_token(user), "token_type": "bearer"}


@router.post("/invitations/{invite_id}/revoke")
async def revoke_invite(
    invite_id: str, user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db)
):
    require_owner(user)
    inv = await db.scalar(select(TeamInvitation).where(
        TeamInvitation.id == invite_id, TeamInvitation.org_id == user.org_id,
        TeamInvitation.accepted_at.is_(None),
        TeamInvitation.revoked_at.is_(None)
    ))
    if not inv:
        raise HTTPException(404, "Invitation not found")
    inv.revoked_at = utc_now()
    await db.commit()
    return {"detail": "Invitation revoked"}


@router.post("/members/{member_id}/deactivate")
async def deactivate_member(
    member_id: str, user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db)
):
    require_owner(user)
    member = await db.scalar(select(User).where(
        User.id == member_id, User.org_id == user.org_id
    ))
    if not member or member.role == "owner":
        raise HTTPException(404, "Member cannot be deactivated")
    member.is_active = False
    member.session_version += 1
    await db.commit()
    return {"detail": "Member access revoked"}
