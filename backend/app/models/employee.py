from datetime import date, datetime
from typing import Optional
import uuid
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TenantMixin, TimestampMixin, UUIDMixin


class Employee(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "employees"

    __table_args__ = (
        UniqueConstraint("organization_id", "employee_code", name="uq_employee_org_code"),
    )

    employee_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone_number: Mapped[str] = mapped_column(String(50), nullable=False)
    photo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    department_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    position_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("positions.id", ondelete="SET NULL"),
        nullable=True,
    )
    location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("locations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    supervisor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
    )

    employment_type: Mapped[str] = mapped_column(
        String(50), default="full_time", nullable=False
    )  # full_time, part_time, contract, temporary
    employment_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    employment_status: Mapped[str] = mapped_column(
        String(32), default="active", nullable=False, index=True
    )  # active, inactive, suspended, on_leave, terminated
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    credential: Mapped[Optional["EmployeeCredential"]] = relationship(
        back_populates="employee", uselist=False, cascade="all, delete-orphan"
    )


class EmployeeCredential(UUIDMixin, TimestampMixin, TenantMixin, Base):
    __tablename__ = "employee_credentials"

    __table_args__ = (
        UniqueConstraint("employee_id", name="uq_employee_credential_emp"),
    )

    employee_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("employees.id", ondelete="CASCADE"),
        nullable=False,
    )
    pin_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    rfid_uid_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    qr_token_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    employee: Mapped["Employee"] = relationship(back_populates="credential")
