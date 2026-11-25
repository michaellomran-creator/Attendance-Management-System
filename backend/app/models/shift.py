from datetime import date, time
from typing import Optional
import uuid
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    JSON,
    String,
    Time,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TenantMixin, TimestampMixin, UUIDMixin


class Shift(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "shifts"

    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_shift_org_name"),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    shift_type: Mapped[str] = mapped_column(
        String(40), default="custom", nullable=False
    )  # morning, afternoon, night, general, rotating, custom
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    crosses_midnight: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    applicable_days: Mapped[list[int]] = mapped_column(
        JSON, default=lambda: [0, 1, 2, 3, 4], nullable=False
    )  # 0=Mon .. 6=Sun
    break_duration_minutes: Mapped[int] = mapped_column(
        Integer, default=60, nullable=False
    )
    grace_period_minutes: Mapped[int] = mapped_column(
        Integer, default=10, nullable=False
    )
    expected_work_minutes: Mapped[int] = mapped_column(
        Integer, default=480, nullable=False
    )
    minimum_work_minutes: Mapped[int] = mapped_column(
        Integer, default=240, nullable=False
    )
    early_departure_threshold_minutes: Mapped[int] = mapped_column(
        Integer, default=15, nullable=False
    )
    overtime_threshold_minutes: Mapped[int] = mapped_column(
        Integer, default=30, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    policy: Mapped[Optional["ShiftPolicy"]] = relationship(
        back_populates="shift", uselist=False, cascade="all, delete-orphan"
    )


class ShiftPolicy(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "shift_policies"

    __table_args__ = (UniqueConstraint("shift_id", name="uq_shift_policy_shift"),)

    shift_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("shifts.id", ondelete="CASCADE"),
        nullable=False,
    )
    overtime_eligible: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    overtime_requires_approval: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    auto_deduct_break: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    mark_absent_after_minutes: Mapped[int] = mapped_column(
        Integer, default=120, nullable=False
    )

    shift: Mapped["Shift"] = relationship(back_populates="policy")


class ShiftAssignment(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "shift_assignments"

    __table_args__ = (
        CheckConstraint(
            "(employee_id IS NOT NULL) OR (department_id IS NOT NULL)",
            name="ck_shift_assignment_target",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_shift_assignment_dates",
        ),
    )

    shift_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("shifts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    employee_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    department_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    is_temporary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rotation_group: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)


class Holiday(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "holidays"

    __table_args__ = (
        UniqueConstraint("organization_id", "holiday_date", name="uq_holiday_org_date"),
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    holiday_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
