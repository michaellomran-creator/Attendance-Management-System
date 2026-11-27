"""Remove subscription plans, subscriptions, and billing grace period.

Revision ID: 0002_remove_subscription_and_billing
Revises: 0001_initial_schema
Create Date: 2026-11-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_remove_subscription_and_billing"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop subscriptions before subscription_plans due to FK on plan_id (RESTRICT)
    op.drop_index(op.f("ix_subscriptions_status"), table_name="subscriptions")
    op.drop_index(op.f("ix_subscriptions_organization_id"), table_name="subscriptions")
    op.drop_table("subscriptions")
    op.drop_table("subscription_plans")
    op.drop_column("platform_settings", "default_grace_period_days")


def downgrade() -> None:
    op.add_column(
        "platform_settings",
        sa.Column(
            "default_grace_period_days",
            sa.Integer(),
            server_default="14",
            nullable=False,
        ),
    )
    op.create_table(
        "subscription_plans",
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("max_employees", sa.Integer(), nullable=False),
        sa.Column("max_locations", sa.Integer(), nullable=False),
        sa.Column("max_admins", sa.Integer(), nullable=False),
        sa.Column("data_retention_days", sa.Integer(), nullable=False),
        sa.Column("monthly_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("support_level", sa.String(length=50), nullable=False),
        sa.Column("features", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("max_admins > 0", name="ck_plan_max_admins"),
        sa.CheckConstraint("max_employees > 0", name="ck_plan_max_employees"),
        sa.CheckConstraint("max_locations > 0", name="ck_plan_max_locations"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "subscriptions",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("billing_cycle", sa.String(length=20), nullable=False),
        sa.Column("payment_status", sa.String(length=32), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=False),
        sa.Column("grace_period_days", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("expiry_date >= start_date", name="ck_subscription_dates"),
        sa.CheckConstraint(
            "grace_period_days >= 0", name="ck_subscription_grace_nonneg"
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"], ["organizations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["plan_id"], ["subscription_plans.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_subscriptions_organization_id"),
        "subscriptions",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_subscriptions_status"), "subscriptions", ["status"], unique=False
    )
