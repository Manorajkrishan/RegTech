"""Organisation-isolated storage. Schema migration tooling needed before production."""
from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import String, Float, DateTime, ForeignKey, Text, Integer, Boolean, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from .config import settings


def new_id():
    return str(uuid4())


def now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Organisation(Base):
    __tablename__ = "organisations"
    __table_args__ = (UniqueConstraint("stripe_customer_id", name="uq_org_stripe_customer_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    subscription_status: Mapped[str] = mapped_column(String(30), nullable=False, default="free")
    subscription_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    subscription_price_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    subscription_event_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organisations.id"), index=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(20), default="owner")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    session_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class TeamInvitation(Base):
    __tablename__ = "team_invitations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organisations.id"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invited_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class BillingEvent(Base):
    __tablename__ = "billing_events"
    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AccountToken(Base):
    """Store only SHA-256 digests, never recovery/verification tokens themselves."""
    __tablename__ = "account_tokens"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Activity(Base):
    __tablename__ = "activities"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organisations.id"), index=True)
    description: Mapped[str] = mapped_column(Text)
    supplier: Mapped[str] = mapped_column(String(200), default="")
    activity_date: Mapped[str] = mapped_column(String(10), default="")
    factor_id: Mapped[str] = mapped_column(String(100))
    factor_year: Mapped[int] = mapped_column(Integer)
    factor_value: Mapped[float] = mapped_column(Float)
    factor_source: Mapped[str] = mapped_column(Text)
    quantity: Mapped[float] = mapped_column(Float)
    unit: Mapped[str] = mapped_column(String(50))
    scope: Mapped[str] = mapped_column(String(10))
    emissions_kg: Mapped[float] = mapped_column(Float)
    evidence_reference: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(12), default="draft")
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    org_id: Mapped[str] = mapped_column(ForeignKey("organisations.id"), index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    activity_id: Mapped[str] = mapped_column(String(36))
    action: Mapped[str] = mapped_column(String(25))
    details: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


engine = create_async_engine(settings.db_url, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_db():
    if settings.environment == "production":
        # Production schema changes are explicit and reviewed: never silently create tables.
        async with engine.connect() as connection:
            try:
                revision = await connection.exec_driver_sql(
                    "SELECT version_num FROM alembic_version"
                )
                if revision.scalar_one_or_none() != "20261021_02":
                    raise RuntimeError("Run 'alembic upgrade head' before starting production")
            except Exception as exc:
                raise RuntimeError("Production DB migration required: alembic upgrade head") from exc
    else:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)


async def get_db():
    async with SessionLocal() as db:
        yield db
