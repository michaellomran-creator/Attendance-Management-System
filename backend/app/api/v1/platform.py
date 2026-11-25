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
from app.models.platform import AuditLog, Subscription, SubscriptionPlan
from app.schemas.platform import (
    AuditLogOut,
    OrganizationOnboardRequest,
    OrganizationOut,
    OrganizationStatusUpdate,
    PlatformAnalyticsOut,
    PlatformSettingsOut,
    PlatformSettingsUpdate,
    SubscriptionOut,
    SubscriptionPlanCreate,
    SubscriptionPlanOut,
    SubscriptionUpdate,
)
from app.services.audit_service import record_audit_log
from app.services.platform_service import (
    create_subscription_plan,
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


@router.get("/plans", response_model=List[SubscriptionPlanOut])
def list_plans(
    _: AuthContext = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> List[SubscriptionPlanOut]:
    plans = db.execute(
        select(SubscriptionPlan).order_by(SubscriptionPlan.monthly_price)
    ).scalars().all()
    return [SubscriptionPlanOut.model_validate(p) for p in plans]


@router.post(
    "/plans",
    response_model=SubscriptionPlanOut,
    status_code=status.HTTP_201_CREATED,
)
def create_plan(
    payload: SubscriptionPlanCreate,
    auth: AuthContext = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> SubscriptionPlanOut:
    plan = create_subscription_plan(db, payload, auth.user.id, auth.user.email)
    return SubscriptionPlanOut.model_validate(plan)


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
        sub = (
            db.execute(
                select(Subscription)
                .where(Subscription.organization_id == org.id)
                .order_by(Subscription.created_at.desc())
            )
            .scalars()
            .first()
        )
        plan = db.get(SubscriptionPlan, sub.plan_id) if sub else None
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
                subscription=SubscriptionOut(
                    id=sub.id,
                    organization_id=sub.organization_id,
                    plan_id=sub.plan_id,
                    plan_name=plan.name if plan else None,
                    status=sub.status,
                    billing_cycle=sub.billing_cycle,
                    payment_status=sub.payment_status,
                    start_date=sub.start_date,
                    expiry_date=sub.expiry_date,
                    grace_period_days=sub.grace_period_days,
                    notes=sub.notes,
                )
                if sub
                else None,
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
    )


@router.patch("/organizations/{organization_id}/subscription", response_model=SubscriptionOut)
def update_organization_subscription(
    organization_id: uuid.UUID,
    payload: SubscriptionUpdate,
    auth: AuthContext = Depends(require_platform_admin),
    db: Session = Depends(get_db),
) -> SubscriptionOut:
    sub = (
        db.execute(
            select(Subscription)
            .where(Subscription.organization_id == organization_id)
            .order_by(Subscription.created_at.desc())
        )
        .scalars()
        .first()
    )
    if not sub:
        raise NotFoundError("Subscription not found for this organization")

    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(sub, field, val)

    record_audit_log(
        db,
        action="platform.subscription_updated",
        entity_type="subscription",
        entity_id=str(sub.id),
        organization_id=organization_id,
        actor_user_id=auth.user.id,
        actor_email=auth.user.email,
        metadata=payload.model_dump(exclude_unset=True, mode="json"),
    )
    db.commit()
    db.refresh(sub)
    plan = db.get(SubscriptionPlan, sub.plan_id)
    return SubscriptionOut(
        id=sub.id,
        organization_id=sub.organization_id,
        plan_id=sub.plan_id,
        plan_name=plan.name if plan else None,
        status=sub.status,
        billing_cycle=sub.billing_cycle,
        payment_status=sub.payment_status,
        start_date=sub.start_date,
        expiry_date=sub.expiry_date,
        grace_period_days=sub.grace_period_days,
        notes=sub.notes,
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
