from datetime import datetime
from typing import Optional
import uuid
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

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
    allow_self_registration: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    maintenance_mode: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
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
