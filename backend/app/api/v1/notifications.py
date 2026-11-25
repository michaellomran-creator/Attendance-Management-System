from typing import List
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import AuthContext, require_org_member
from app.core.exceptions import NotFoundError
from app.models.requests import Notification
from app.schemas.requests import NotificationOut

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=List[NotificationOut])
def list_notifications(
    auth: AuthContext = Depends(require_org_member),
    db: Session = Depends(get_db),
) -> List[NotificationOut]:
    rows = (
        db.execute(
            select(Notification)
            .where(
                Notification.organization_id == auth.organization_id,
                Notification.user_id == auth.user.id,
            )
            .order_by(Notification.created_at.desc())
            .limit(50)
        )
        .scalars()
        .all()
    )
    return [NotificationOut.model_validate(n) for n in rows]


@router.patch("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_notification_read(
    notification_id: uuid.UUID,
    auth: AuthContext = Depends(require_org_member),
    db: Session = Depends(get_db),
) -> None:
    notif = db.get(Notification, notification_id)
    if (
        not notif
        or notif.organization_id != auth.organization_id
        or notif.user_id != auth.user.id
    ):
        raise NotFoundError("Notification not found")
    notif.is_read = True
    db.commit()
