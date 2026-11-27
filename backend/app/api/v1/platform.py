from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import (
    AuthContext,
    get_client_ip,
    require_platform_admin,
)
from app.core.exceptions import NotFoundError
from app.models.employee import Employee
from app.models.organization import Organization
from app.models.platform import AuditLog
from app.schemas.platform import (
    AuditLogOut,
    OrganizationOnboardRequest,
    OrganizationOut,
    OrganizationStatusUpdate,
    PlatformAnalyticsOut,
    PlatformSettingsOut,
    PlatformSettingsUpdate,
)
from app.services.audit_service import record_audit_log
from app.services.platform_service import (
    get_or_create_platform_settings,
    get_platform_analytics,
    onboard_organization,
)

router = APIRouter(prefix="/platform", tags=["Platform Administration"])


@router.get("/analytics", response_model=PlatformAnalyticsOut)
def platform_analytics(
    _: AuthContext = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> PlatformAnalyticsOut:
    return get_platform_analytics(db)


@router.get("/organizations", response_model=List[OrganizationOut])
def list_organizations(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    search: Optional[str] = Query(default=None),
    _: AuthContext = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> List[OrganizationOut]:
    query = select(Organization).order_by(Organization.created_at.desc())
    if status_filter:
        query = query.where(Organization.status == status_filter)
    if search:
        like = f"%{search.strip()}%"
        query = query.where(
            Organization.name.ilike(like) | Organization.business_email.ilike(like)
        )
    orgs = db.execute(query).scalars().all()

    results: List[OrganizationOut] = []
    for org in orgs:
        active_emp = db.execute(
            select(func.count(Employee.id)).where(
                Employee.organization_id == org.id,
                Employee.employment_status == "active",
            )
        ).scalar_one()
        results.append(
            OrganizationOut(
                id=org.id,
                name=org.name,
                slug=org.slug,
                organization_type=org.organization_type,
                contact_person=org.contact_person,
                business_email=org.business_email,
                phone_number=org.phone_number,
                country=org.country,
                timezone=org.timezone,
                address=org.address,
                estimated_employees=org.estimated_employees,
                status=org.status,
                created_at=org.created_at,
                active_employees_count=active_emp,
            )
        )
    return results


@router.post(
    "/organizations",
    response_model=OrganizationOut,
    status_code=status.HTTP_201_CREATED,
)
def onboard_org(
    payload: OrganizationOnboardRequest,
    request: Request,
    auth: AuthContext = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> OrganizationOut:
    return onboard_organization(
        db,
        payload,
        actor_user_id=auth.user.id,
        actor_email=auth.user.email,
        ip_address=get_client_ip(request),
    )


@router.patch("/organizations/{organization_id}/status", response_model=OrganizationOut)
def update_organization_status(
    organization_id: uuid.UUID,
    payload: OrganizationStatusUpdate,
    auth: AuthContext = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> OrganizationOut:
    org = db.get(Organization, organization_id)
    if not org:
        raise NotFoundError("Organization not found")

    previous = org.status
    org.status = payload.status
    record_audit_log(
        db,
        action="platform.organization_status_updated",
        entity_type="organization",
        entity_id=str(org.id),
        organization_id=org.id,
        actor_user_id=auth.user.id,
        actor_email=auth.user.email,
        reason=payload.reason,
        metadata={"previous_status": previous, "new_status": payload.status},
    )
    db.commit()
    db.refresh(org)

    active_emp = db.execute(
        select(func.count(Employee.id)).where(
            Employee.organization_id == org.id,
            Employee.employment_status == "active",
        )
    ).scalar_one()

    return OrganizationOut(
        id=org.id,
        name=org.name,
        slug=org.slug,
        organization_type=org.organization_type,
        contact_person=org.contact_person,
        business_email=org.business_email,
        phone_number=org.phone_number,
        country=org.country,
        timezone=org.timezone,
        address=org.address,
        estimated_employees=org.estimated_employees,
        status=org.status,
        created_at=org.created_at,
        active_employees_count=active_emp,
    )


@router.get("/settings", response_model=PlatformSettingsOut)
def get_platform_settings(
    _: AuthContext = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> PlatformSettingsOut:
    return PlatformSettingsOut.model_validate(get_or_create_platform_settings(db))


@router.patch("/settings", response_model=PlatformSettingsOut)
def update_platform_settings(
    payload: PlatformSettingsUpdate,
    auth: AuthContext = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> PlatformSettingsOut:
    ps = get_or_create_platform_settings(db)
    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(ps, field, val)
    record_audit_log(
        db,
        action="platform.settings_updated",
        entity_type="platform_settings",
        entity_id=str(ps.id),
        actor_user_id=auth.user.id,
        actor_email=auth.user.email,
    )
    db.commit()
    db.refresh(ps)
    return PlatformSettingsOut.model_validate(ps)


@router.get("/audit-logs", response_model=List[AuditLogOut])
def list_platform_audit_logs(
    limit: int = Query(default=100, ge=1, le=500),
    _: AuthContext = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> List[AuditLogOut]:
    logs = (
        db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit))
        .scalars()
        .all()
    )
    return [AuditLogOut.model_validate(item) for item in logs]
