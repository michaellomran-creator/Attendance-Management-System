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
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TenantMixin, TimestampMixin, UUIDMixin, utc_now


class AttendanceTerminal(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "attendance_terminals"

    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_terminal_org_name"),
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    device_identifier: Mapped[str] = mapped_column(
        String(120), unique=True, nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("locations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AttendanceSession(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "attendance_sessions"

    employee_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    shift_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("shifts.id", ondelete="SET NULL"),
        nullable=True,
    )
    location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("locations.id", ondelete="SET NULL"),
        nullable=True,
    )
    terminal_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("attendance_terminals.id", ondelete="SET NULL"),
        nullable=True,
    )
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    check_in_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    check_out_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(32), default="present", nullable=False, index=True
    )  # present, late, on_time, early_departure, incomplete, overtime, absent, on_leave, holiday, rest_day
    is_open: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    is_late: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    late_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_early_departure: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    early_departure_minutes: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    gross_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    break_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    net_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    overtime_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    overtime_approved: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    events: Mapped[list["AttendanceEvent"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    breaks: Mapped[list["BreakRecord"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("gross_minutes >= 0", name="ck_session_gross_nonneg"),
        CheckConstraint("break_minutes >= 0", name="ck_session_break_nonneg"),
        CheckConstraint("net_minutes >= 0", name="ck_session_net_nonneg"),
        CheckConstraint("overtime_minutes >= 0", name="ck_session_overtime_nonneg"),
        CheckConstraint(
            "check_out_at IS NULL OR check_out_at >= check_in_at",
            name="ck_session_checkout_after_checkin",
        ),
        Index(
            "ix_attendance_sessions_org_work_date",
            "organization_id",
            "work_date",
        ),
        Index(
            "ix_attendance_sessions_org_emp_date",
            "organization_id",
            "employee_id",
            "work_date",
        ),
        Index(
            "uq_one_open_session_per_employee",
            "employee_id",
            unique=True,
            postgresql_where=text("is_open = true"),
            sqlite_where=text("is_open = 1"),
        ),
    )


class AttendanceEvent(UUIDMixin, TenantMixin, Base):
    """Immutable historical attendance event log."""

    __tablename__ = "attendance_events"

    __table_args__ = (
        Index(
            "ix_attendance_events_org_emp_ts",
            "organization_id",
            "employee_id",
            "event_timestamp",
        ),
    )

    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("attendance_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("locations.id", ondelete="SET NULL"),
        nullable=True,
    )
    terminal_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("attendance_terminals.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )  # check_in, check_out, break_start, break_end, correction
    event_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(
        String(40), default="terminal_pin", nullable=False
    )  # terminal_pin, web_employee, admin_correction
    event_status: Mapped[str] = mapped_column(
        String(32), default="recorded", nullable=False
    )  # recorded, superseded
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    session: Mapped[Optional["AttendanceSession"]] = relationship(back_populates="events")


class BreakRecord(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "break_records"

    __table_args__ = (
        CheckConstraint(
            "break_end_at IS NULL OR break_end_at >= break_start_at",
            name="ck_break_end_after_start",
        ),
        Index(
            "uq_one_open_break_per_session",
            "session_id",
            unique=True,
            postgresql_where=text("is_open = true"),
            sqlite_where=text("is_open = 1"),
        ),
    )

    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("attendance_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    break_start_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    break_end_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_open: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    session: Mapped["AttendanceSession"] = relationship(back_populates="breaks")


class AttendanceSummary(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "attendance_summaries"

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "employee_id", "summary_date", name="uq_summary_emp_date"
        ),
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    summary_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    primary_status: Mapped[str] = mapped_column(String(32), nullable=False)
    total_gross_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_break_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_net_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_overtime_minutes: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    late_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
