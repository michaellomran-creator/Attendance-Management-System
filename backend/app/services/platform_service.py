from datetime import date, datetime, timedelta, timezone
import re
from typing import Optional
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import hash_secret
from app.models.attendance import AttendanceSession
from app.models.employee import Employee
from app.models.organization import Organization, OrganizationSettings
from app.models.platform import PlatformSettings, Subscription, SubscriptionPlan
from app.models.requests import LeaveType
from app.models.user import User, UserRole
from app.schemas.platform import (
    OrganizationOnboardRequest,
    OrganizationOut,
    PlatformAnalyticsOut,
    SubscriptionOut,
    SubscriptionPlanCreate,
)
from app.services.audit_service import record_audit_log
from app.services.rbac_service import initialize_organization_roles


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or f"org-{uuid.uuid4().hex[:8]}"


def onboard_organization(
    db: Session,
    payload: OrganizationOnboardRequest,
    *,
    actor_user_id: uuid.UUID,
    actor_email: str,
    ip_address: Optional[str] = None,
) -> OrganizationOut:
    plan = db.get(SubscriptionPlan, payload.plan_id)
    if not plan or not plan.is_active:
        raise NotFoundError("Selected subscription plan does not exist or is inactive")

    existing_user = (
        db.execute(
            select(User).where(User.email == payload.admin_email.lower().strip())
        )
        .scalars()
        .first()
    )
    if existing_user:
        raise ConflictError("An account with this administrator email already exists")

    base_slug = _slugify(payload.name)
    slug = base_slug
    counter = 1
    while (
        db.execute(select(Organization).where(Organization.slug == slug))
        .scalars()
        .first()
        is not None
    ):
        counter += 1
        slug = f"{base_slug}-{counter}"

    org = Organization(
        name=payload.name.strip(),
        slug=slug,
        organization_type=payload.organization_type.strip(),
        contact_person=payload.contact_person.strip(),
        business_email=payload.business_email.lower().strip(),
        phone_number=payload.phone_number.strip(),
        country=payload.country.strip(),
        timezone=payload.timezone.strip(),
        address=payload.address,
        estimated_employees=payload.estimated_employees,
        status="active",
    )
    db.add(org)
    db.flush()

    org_settings = OrganizationSettings(organization_id=org.id)
    db.add(org_settings)

    roles = initialize_organization_roles(db, org.id)

    admin_user = User(
        organization_id=org.id,
        email=payload.admin_email.lower().strip(),
        full_name=payload.admin_full_name.strip(),
        password_hash=hash_secret(payload.admin_password),
        is_platform_admin=False,
        is_active=True,
    )
    db.add(admin_user)
    db.flush()
    db.add(UserRole(user_id=admin_user.id, role_id=roles["org_admin"].id))

    today = date.today()
    days = 365 if payload.billing_cycle == "annual" else 30
    subscription = Subscription(
        organization_id=org.id,
        plan_id=plan.id,
        status="active",
        billing_cycle=payload.billing_cycle,
        payment_status="paid",
        start_date=today,
        expiry_date=today + timedelta(days=days),
        grace_period_days=14,
    )
    db.add(subscription)

    # Seed default leave types for the new organization
    default_leave_types = [
        ("Annual Leave", "ANNUAL", True, 20),
        ("Sick Leave", "SICK", True, 12),
        ("Personal Leave", "PERSONAL", False, 5),
        ("Unpaid Leave", "UNPAID", False, None),
    ]
    for lt_name, lt_code, is_paid, max_days in default_leave_types:
        db.add(
            LeaveType(
                organization_id=org.id,
                name=lt_name,
                code=lt_code,
                is_paid=is_paid,
                max_days_per_year=max_days,
            )
        )

    record_audit_log(
        db,
        action="platform.organization_onboarded",
        entity_type="organization",
        entity_id=str(org.id),
        organization_id=org.id,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        ip_address=ip_address,
        metadata={
            "organization_name": org.name,
            "plan_code": plan.code,
            "admin_email": admin_user.email,
        },
    )
    db.commit()
    db.refresh(org)
    db.refresh(subscription)

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
        active_employees_count=0,
        subscription=SubscriptionOut(
            id=subscription.id,
            organization_id=subscription.organization_id,
            plan_id=subscription.plan_id,
            plan_name=plan.name,
            status=subscription.status,
            billing_cycle=subscription.billing_cycle,
            payment_status=subscription.payment_status,
            start_date=subscription.start_date,
            expiry_date=subscription.expiry_date,
            grace_period_days=subscription.grace_period_days,
            notes=subscription.notes,
        ),
    )


def create_subscription_plan(
    db: Session, payload: SubscriptionPlanCreate, actor_user_id: uuid.UUID, actor_email: str
) -> SubscriptionPlan:
    existing = (
        db.execute(
            select(SubscriptionPlan).where(SubscriptionPlan.code == payload.code.lower())
        )
        .scalars()
        .first()
    )
    if existing:
        raise ConflictError("Subscription plan code already exists")

    plan = SubscriptionPlan(
        code=payload.code.lower().strip(),
        name=payload.name.strip(),
        description=payload.description,
        max_employees=payload.max_employees,
        max_locations=payload.max_locations,
        max_admins=payload.max_admins,
        data_retention_days=payload.data_retention_days,
        monthly_price=payload.monthly_price,
        currency=payload.currency,
        support_level=payload.support_level,
        features=payload.features,
    )
    db.add(plan)
    record_audit_log(
        db,
        action="platform.plan_created",
        entity_type="subscription_plan",
        entity_id=plan.code,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
    )
    db.commit()
    db.refresh(plan)
    return plan


def get_platform_analytics(db: Session) -> PlatformAnalyticsOut:
    total_orgs = db.execute(select(func.count(Organization.id))).scalar_one()
    active_orgs = db.execute(
        select(func.count(Organization.id)).where(Organization.status == "active")
    ).scalar_one()
    suspended_orgs = db.execute(
        select(func.count(Organization.id)).where(Organization.status == "suspended")
    ).scalar_one()
    total_active_employees = db.execute(
        select(func.count(Employee.id)).where(Employee.employment_status == "active")
    ).scalar_one()

    today_utc = datetime.now(timezone.utc).date()
    sessions_today = db.execute(
        select(func.count(AttendanceSession.id)).where(
            AttendanceSession.work_date == today_utc
        )
    ).scalar_one()

    sub_rows = db.execute(
        select(Subscription.status, func.count(Subscription.id)).group_by(
            Subscription.status
        )
    ).all()
    type_rows = db.execute(
        select(Organization.organization_type, func.count(Organization.id)).group_by(
            Organization.organization_type
        )
    ).all()

    return PlatformAnalyticsOut(
        total_organizations=total_orgs,
        active_organizations=active_orgs,
        suspended_organizations=suspended_orgs,
        total_active_employees=total_active_employees,
        total_attendance_sessions_today=sessions_today,
        subscriptions_by_status={row[0]: row[1] for row in sub_rows},
        organizations_by_type={row[0]: row[1] for row in type_rows},
    )


def get_or_create_platform_settings(db: Session) -> PlatformSettings:
    ps = db.execute(select(PlatformSettings)).scalars().first()
    if not ps:
        ps = PlatformSettings()
        db.add(ps)
        db.commit()
        db.refresh(ps)
    return ps
