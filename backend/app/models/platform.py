from datetime import date, datetime
from typing import Optional
import uuid
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin, utc_now


class PlatformSettings(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "platform_settings"

    platform_name: Mapped[str] = mapped_column(
        String(150), default="NORAM Attendance Platform", nullable=False
    )
    support_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    default_timezone: Mapped[str] = mapped_column(
        String(64), default="Africa/Addis_Ababa", nullable=False
    )
    default_grace_period_days: Mapped[int] = mapped_column(
        Integer, default=14, nullable=False
    )
    allow_self_registration: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    maintenance_mode: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )


class SubscriptionPlan(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "subscription_plans"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    max_employees: Mapped[int] = mapped_column(Integer, nullable=False)
    max_locations: Mapped[int] = mapped_column(Integer, nullable=False)
    max_admins: Mapped[int] = mapped_column(Integer, nullable=False)
    data_retention_days: Mapped[int] = mapped_column(
        Integer, default=1095, nullable=False
    )
    monthly_price: Mapped[float] = mapped_column(
        Numeric(12, 2), default=0, nullable=False
    )
    currency: Mapped[str] = mapped_column(String(10), default="ETB", nullable=False)
    support_level: Mapped[str] = mapped_column(
        String(50), default="standard", nullable=False
    )
    features: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="plan")

    __table_args__ = (
        CheckConstraint("max_employees > 0", name="ck_plan_max_employees"),
        CheckConstraint("max_locations > 0", name="ck_plan_max_locations"),
        CheckConstraint("max_admins > 0", name="ck_plan_max_admins"),
    )


class Subscription(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "subscriptions"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("subscription_plans.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32), default="active", nullable=False, index=True
    )  # trial, active, past_due, suspended, cancelled, expired
    billing_cycle: Mapped[str] = mapped_column(
        String(20), default="monthly", nullable=False
    )  # monthly, annual, custom
    payment_status: Mapped[str] = mapped_column(
        String(32), default="paid", nullable=False
    )  # paid, pending, overdue, waived
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    grace_period_days: Mapped[int] = mapped_column(Integer, default=14, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    organization: Mapped["Organization"] = relationship(back_populates="subscriptions")
    plan: Mapped["SubscriptionPlan"] = relationship(back_populates="subscriptions")

    __table_args__ = (
        CheckConstraint("expiry_date >= start_date", name="ck_subscription_dates"),
        CheckConstraint("grace_period_days >= 0", name="ck_subscription_grace_nonneg"),
    )


class AuditLog(UUIDMixin, Base):
    __tablename__ = "audit_logs"

    __table_args__ = (
        Index("ix_audit_logs_org_created", "organization_id", "created_at"),
    )

    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
