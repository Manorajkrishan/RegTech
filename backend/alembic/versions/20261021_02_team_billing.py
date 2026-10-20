"""Team invitations and subscription status, additive to 20261020_01.

Revision ID: 20261021_02
Revises: 20261020_01
"""
from alembic import op
import sqlalchemy as sa

revision = "20261021_02"
down_revision = "20261020_01"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("organisations", sa.Column("stripe_customer_id", sa.String(100), nullable=True))
    op.add_column("organisations", sa.Column("subscription_status", sa.String(30), nullable=False, server_default="free"))
    op.add_column("organisations", sa.Column("subscription_id", sa.String(100), nullable=True))
    op.add_column("organisations", sa.Column("subscription_price_id", sa.String(100), nullable=True))
    op.add_column("organisations", sa.Column("subscription_event_created", sa.Integer(), nullable=False, server_default="0"))
    op.create_unique_constraint("uq_org_stripe_customer_id", "organisations", ["stripe_customer_id"])
    op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_table(
        "team_invitations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organisations.id"), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invited_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_team_invitations_org_id", "team_invitations", ["org_id"])
    op.create_table(
        "billing_events",
        sa.Column("id", sa.String(120), primary_key=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("billing_events")
    op.drop_index("ix_team_invitations_org_id", table_name="team_invitations")
    op.drop_table("team_invitations")
    op.drop_column("users", "is_active")
    op.drop_constraint("uq_org_stripe_customer_id", "organisations", type_="unique")
    op.drop_column("organisations", "subscription_event_created")
    op.drop_column("organisations", "subscription_price_id")
    op.drop_column("organisations", "subscription_id")
    op.drop_column("organisations", "subscription_status")
    op.drop_column("organisations", "stripe_customer_id")
