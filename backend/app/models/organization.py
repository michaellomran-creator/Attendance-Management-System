from typing import Optional
import uuid
from sqlalchemy import (
    Boolean,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TenantMixin, TimestampMixin, UUIDMixin


class Organization(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    organization_type: Mapped[str] = mapped_column(
        String(80), nullable=False
    )  # hotel, hospital, factory, restaurant, school, office, retail, construction, ngo, other
    contact_person: Mapped[str] = mapped_column(String(150), nullable=False)
    business_email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(50), nullable=False)
    country: Mapped[str] = mapped_column(String(100), default="Ethiopia", nullable=False)
    timezone: Mapped[str] = mapped_column(
        String(64), default="Africa/Addis_Ababa", nullable=False
    )
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    estimated_employees: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    logo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), default="active", nullable=False, index=True
    )  # active, suspended, inactive

    settings: Mapped[Optional["OrganizationSettings"]] = relationship(
        back_populates="organization", uselist=False, cascade="all, delete-orphan"
    )
    subscriptions: Mapped[list["Subscription"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    departments: Mapped[list["Department"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    locations: Mapped[list["Location"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    positions: Mapped[list["Position"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )


class OrganizationSettings(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "organization_settings"

    __table_args__ = (
        UniqueConstraint("organization_id", name="uq_org_settings_org_id"),
    )

    default_grace_period_minutes: Mapped[int] = mapped_column(
        Integer, default=10, nullable=False
    )
    default_expected_work_minutes: Mapped[int] = mapped_column(
        Integer, default=480, nullable=False
    )
    default_minimum_work_minutes: Mapped[int] = mapped_column(
        Integer, default=240, nullable=False
    )
    default_early_departure_threshold_minutes: Mapped[int] = mapped_column(
        Integer, default=15, nullable=False
    )
    break_tracking_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    default_break_minutes: Mapped[int] = mapped_column(
        Integer, default=60, nullable=False
    )
    overtime_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    overtime_requires_approval: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    terminal_reset_delay_seconds: Mapped[int] = mapped_column(
        Integer, default=4, nullable=False
    )
    workweek_days: Mapped[list[int]] = mapped_column(
        JSON, default=lambda: [0, 1, 2, 3, 4], nullable=False
    )  # 0=Mon .. 6=Sun
    allow_employee_correction_requests: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    organization: Mapped["Organization"] = relationship(back_populates="settings")


class Department(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "departments"

    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_department_org_name"),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    manager_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    organization: Mapped["Organization"] = relationship(back_populates="departments")


class Position(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "positions"

    __table_args__ = (
        UniqueConstraint("organization_id", "title", name="uq_position_org_title"),
    )

    title: Mapped[str] = mapped_column(String(120), nullable=False)
    department_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    organization: Mapped["Organization"] = relationship(back_populates="positions")


class Location(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "locations"

    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_location_org_name"),
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timezone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    organization: Mapped["Organization"] = relationship(back_populates="locations")
