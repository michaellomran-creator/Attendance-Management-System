from typing import Any, Dict, Optional
import uuid
from sqlalchemy.orm import Session

from app.models.platform import AuditLog


def record_audit_log(
    db: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: Optional[str] = None,
    organization_id: Optional[uuid.UUID] = None,
    actor_user_id: Optional[uuid.UUID] = None,
    actor_email: Optional[str] = None,
    reason: Optional[str] = None,
    ip_address: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> AuditLog:
    """Create an immutable audit log entry within the current transaction."""
    log = AuditLog(
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        reason=reason,
        ip_address=ip_address,
        metadata_json=metadata or {},
    )
    db.add(log)
    return log
