from typing import List
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.dependencies import (
    AuthContext,
    require_org_member,
    require_permissions,
)
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.security import hash_secret
from app.models.organization import (
    Department,
    Location,
    Organization,
    OrganizationSettings,
    Position,
)
from app.models.platform import AuditLog
from app.models.user import User, UserRole
from app.schemas.organization import (
    DepartmentCreate,
    DepartmentOut,
    DepartmentUpdate,
    LocationCreate,
    LocationOut,
    LocationUpdate,
    OrgUserCreate,
    OrgUserOut,
    OrgUserUpdate,
    OrganizationProfileUpdate,
    OrganizationSettingsOut,
    OrganizationSettingsUpdate,
    PositionCreate,
    PositionOut,
)
from app.schemas.platform import AuditLogOut
from app.services.audit_service import record_audit_log
from app.services.rbac_service import get_org_role_by_code

router = APIRouter(prefix="/organizations", tags=["Organization & Structure"])


@router.get("/profile")
def get_organization_profile(
    auth: AuthContext = Depends(require_org_member),
    db: Session = Depends(get_db),
) -> dict:
    org = db.get(Organization, auth.organization_id)
    if not org:
        raise NotFoundError("Organization not found")
    return {
        "id": org.id,
        "name": org.name,
        "slug": org.slug,
        "organization_type": org.organization_type,
        "contact_person": org.contact_person,
        "business_email": org.business_email,
        "phone_number": org.phone_number,
        "country": org.country,
        "timezone": org.timezone,
        "address": org.address,
        "status": org.status,
    }


@router.patch("/profile")
def update_organization_profile(
    payload: OrganizationProfileUpdate,
    auth: AuthContext = Depends(require_permissions("org:manage_settings")),
    db: Session = Depends(get_db),
) -> dict:
    org = db.get(Organization, auth.organization_id)
    if not org:
        raise NotFoundError("Organization not found")
    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(org, field, val)
    record_audit_log(
        db,
        action="organization.profile_updated",
        entity_type="organization",
        entity_id=str(org.id),
        organization_id=org.id,
        actor_user_id=auth.user.id,
        actor_email=auth.user.email,
    )
    db.commit()
    db.refresh(org)
    return {
        "id": org.id,
        "name": org.name,
        "timezone": org.timezone,
        "contact_person": org.contact_person,
        "business_email": org.business_email,
        "phone_number": org.phone_number,
    }


@router.get("/settings", response_model=OrganizationSettingsOut)
def get_org_settings(
    auth: AuthContext = Depends(require_org_member),
    db: Session = Depends(get_db),
) -> OrganizationSettingsOut:
    settings_obj = (
        db.execute(
            select(OrganizationSettings).where(
                OrganizationSettings.organization_id == auth.organization_id
            )
        )
        .scalars()
        .first()
    )
    if not settings_obj:
        settings_obj = OrganizationSettings(organization_id=auth.organization_id)
        db.add(settings_obj)
        db.commit()
        db.refresh(settings_obj)
    return OrganizationSettingsOut.model_validate(settings_obj)


@router.patch("/settings", response_model=OrganizationSettingsOut)
def update_org_settings(
    payload: OrganizationSettingsUpdate,
    auth: AuthContext = Depends(require_permissions("org:manage_settings")),
    db: Session = Depends(get_db),
) -> OrganizationSettingsOut:
    settings_obj = (
        db.execute(
            select(OrganizationSettings).where(
                OrganizationSettings.organization_id == auth.organization_id
            )
        )
        .scalars()
        .first()
    )
    if not settings_obj:
        settings_obj = OrganizationSettings(organization_id=auth.organization_id)
        db.add(settings_obj)
        db.flush()

    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(settings_obj, field, val)

    record_audit_log(
        db,
        action="organization.settings_updated",
        entity_type="organization_settings",
        entity_id=str(settings_obj.id),
        organization_id=auth.organization_id,
        actor_user_id=auth.user.id,
        actor_email=auth.user.email,
    )
    db.commit()
    db.refresh(settings_obj)
    return OrganizationSettingsOut.model_validate(settings_obj)


# --- Departments ---
@router.get("/departments", response_model=List[DepartmentOut])
def list_departments(
    auth: AuthContext = Depends(require_org_member),
    db: Session = Depends(get_db),
) -> List[DepartmentOut]:
    rows = (
        db.execute(
            select(Department)
            .where(Department.organization_id == auth.organization_id)
            .order_by(Department.name)
        )
        .scalars()
        .all()
    )
    return [DepartmentOut.model_validate(d) for d in rows]


@router.post(
    "/departments",
    response_model=DepartmentOut,
    status_code=status.HTTP_201_CREATED,
)
def create_department(
    payload: DepartmentCreate,
    auth: AuthContext = Depends(require_permissions("dept:manage")),
    db: Session = Depends(get_db),
) -> DepartmentOut:
    if payload.manager_user_id is not None:
        mgr = db.get(User, payload.manager_user_id)
        if not mgr or mgr.organization_id != auth.organization_id:
            raise NotFoundError("Selected manager does not belong to this organization")
    dept = Department(
        organization_id=auth.organization_id,
        name=payload.name.strip(),
        code=payload.code.strip() if payload.code else None,
        description=payload.description,
        manager_user_id=payload.manager_user_id,
    )
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return DepartmentOut.model_validate(dept)


@router.patch("/departments/{department_id}", response_model=DepartmentOut)
def update_department(
    department_id: uuid.UUID,
    payload: DepartmentUpdate,
    auth: AuthContext = Depends(require_permissions("dept:manage")),
    db: Session = Depends(get_db),
) -> DepartmentOut:
    dept = db.get(Department, department_id)
    if not dept or dept.organization_id != auth.organization_id:
        raise NotFoundError("Department not found")
    data = payload.model_dump(exclude_unset=True)
    if data.get("manager_user_id") is not None:
        mgr = db.get(User, data["manager_user_id"])
        if not mgr or mgr.organization_id != auth.organization_id:
            raise NotFoundError("Selected manager does not belong to this organization")
    for field, val in data.items():
        setattr(dept, field, val)
    db.commit()
    db.refresh(dept)
    return DepartmentOut.model_validate(dept)


# --- Locations ---
@router.get("/locations", response_model=List[LocationOut])
def list_locations(
    auth: AuthContext = Depends(require_org_member),
    db: Session = Depends(get_db),
) -> List[LocationOut]:
    rows = (
        db.execute(
            select(Location)
            .where(Location.organization_id == auth.organization_id)
            .order_by(Location.name)
        )
        .scalars()
        .all()
    )
    return [LocationOut.model_validate(l) for l in rows]


@router.post(
    "/locations",
    response_model=LocationOut,
    status_code=status.HTTP_201_CREATED,
)
def create_location(
    payload: LocationCreate,
    auth: AuthContext = Depends(require_permissions("location:manage")),
    db: Session = Depends(get_db),
) -> LocationOut:
    loc = Location(
        organization_id=auth.organization_id,
        name=payload.name.strip(),
        code=payload.code.strip() if payload.code else None,
        address=payload.address,
        timezone=payload.timezone,
    )
    db.add(loc)
    db.commit()
    db.refresh(loc)
    return LocationOut.model_validate(loc)


@router.patch("/locations/{location_id}", response_model=LocationOut)
def update_location(
    location_id: uuid.UUID,
    payload: LocationUpdate,
    auth: AuthContext = Depends(require_permissions("location:manage")),
    db: Session = Depends(get_db),
) -> LocationOut:
    loc = db.get(Location, location_id)
    if not loc or loc.organization_id != auth.organization_id:
        raise NotFoundError("Location not found")
    for field, val in payload.model_dump(exclude_unset=True).items():
        setattr(loc, field, val)
    db.commit()
    db.refresh(loc)
    return LocationOut.model_validate(loc)


# --- Positions ---
@router.get("/positions", response_model=List[PositionOut])
def list_positions(
    auth: AuthContext = Depends(require_org_member),
    db: Session = Depends(get_db),
) -> List[PositionOut]:
    rows = (
        db.execute(
            select(Position)
            .where(Position.organization_id == auth.organization_id)
            .order_by(Position.title)
        )
        .scalars()
        .all()
    )
    return [PositionOut.model_validate(p) for p in rows]


@router.post(
    "/positions",
    response_model=PositionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_position(
    payload: PositionCreate,
    auth: AuthContext = Depends(require_permissions("position:manage")),
    db: Session = Depends(get_db),
) -> PositionOut:
    if payload.department_id is not None:
        dept = db.get(Department, payload.department_id)
        if not dept or dept.organization_id != auth.organization_id:
            raise NotFoundError("Selected department does not belong to this organization")
    pos = Position(
        organization_id=auth.organization_id,
        title=payload.title.strip(),
        department_id=payload.department_id,
        description=payload.description,
    )
    db.add(pos)
    db.commit()
    db.refresh(pos)
    return PositionOut.model_validate(pos)


# --- Organization Users ---
@router.get("/users", response_model=List[OrgUserOut])
def list_org_users(
    auth: AuthContext = Depends(require_permissions("org:manage_users")),
    db: Session = Depends(get_db),
) -> List[OrgUserOut]:
    users = (
        db.execute(
            select(User)
            .options(selectinload(User.user_roles).selectinload(UserRole.role))
            .where(User.organization_id == auth.organization_id)
            .order_by(User.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [
        OrgUserOut(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            is_active=u.is_active,
            roles=[ur.role.code for ur in u.user_roles if ur.role],
            assigned_department_ids=[
                uuid.UUID(str(d)) for d in (u.assigned_department_ids or [])
            ],
            last_login_at=u.last_login_at,
            created_at=u.created_at,
        )
        for u in users
    ]


@router.post(
    "/users",
    response_model=OrgUserOut,
    status_code=status.HTTP_201_CREATED,
)
def create_org_user(
    payload: OrgUserCreate,
    auth: AuthContext = Depends(require_permissions("org:manage_users")),
    db: Session = Depends(get_db),
) -> OrgUserOut:
    existing = (
        db.execute(select(User).where(User.email == payload.email.lower().strip()))
        .scalars()
        .first()
    )
    if existing:
        raise ConflictError("Email is already registered")

    role = get_org_role_by_code(db, auth.organization_id, payload.role_code)
    if not role:
        raise NotFoundError("Role not found for this organization")

    for dept_id in payload.assigned_department_ids:
        dept = db.get(Department, dept_id)
        if not dept or dept.organization_id != auth.organization_id:
            raise NotFoundError("Assigned department does not belong to this organization")

    user = User(
        organization_id=auth.organization_id,
        email=payload.email.lower().strip(),
        full_name=payload.full_name.strip(),
        password_hash=hash_secret(payload.password),
        is_platform_admin=False,
        is_active=True,
        assigned_department_ids=[str(d) for d in payload.assigned_department_ids],
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, role_id=role.id))

    record_audit_log(
        db,
        action="organization.user_created",
        entity_type="user",
        entity_id=str(user.id),
        organization_id=auth.organization_id,
        actor_user_id=auth.user.id,
        actor_email=auth.user.email,
        metadata={"role": payload.role_code, "target_email": user.email},
    )
    db.commit()
    db.refresh(user)

    return OrgUserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        roles=[payload.role_code],
        assigned_department_ids=payload.assigned_department_ids,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
    )


@router.patch("/users/{user_id}", response_model=OrgUserOut)
def update_org_user(
    user_id: uuid.UUID,
    payload: OrgUserUpdate,
    auth: AuthContext = Depends(require_permissions("org:manage_users")),
    db: Session = Depends(get_db),
) -> OrgUserOut:
    user = db.get(User, user_id)
    if not user or user.organization_id != auth.organization_id:
        raise NotFoundError("User not found")
    if user.id == auth.user.id and payload.is_active is False:
        raise ForbiddenError("You cannot deactivate your own account")

    if payload.full_name is not None:
        user.full_name = payload.full_name.strip()
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.assigned_department_ids is not None:
        for dept_id in payload.assigned_department_ids:
            dept = db.get(Department, dept_id)
            if not dept or dept.organization_id != auth.organization_id:
                raise NotFoundError("Assigned department does not belong to this organization")
        user.assigned_department_ids = [str(d) for d in payload.assigned_department_ids]
    if payload.role_code is not None:
        role = get_org_role_by_code(db, auth.organization_id, payload.role_code)
        if not role:
            raise NotFoundError("Role not found")
        for existing_ur in list(user.user_roles):
            db.delete(existing_ur)
        db.flush()
        db.add(UserRole(user_id=user.id, role_id=role.id))

    record_audit_log(
        db,
        action="organization.user_updated",
        entity_type="user",
        entity_id=str(user.id),
        organization_id=auth.organization_id,
        actor_user_id=auth.user.id,
        actor_email=auth.user.email,
    )
    db.commit()
    db.refresh(user)

    roles = [
        ur.role.code
        for ur in db.execute(
            select(UserRole)
            .options(selectinload(UserRole.role))
            .where(UserRole.user_id == user.id)
        )
        .scalars()
        .all()
        if ur.role
    ]
    return OrgUserOut(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        roles=roles,
        assigned_department_ids=[
            uuid.UUID(str(d)) for d in (user.assigned_department_ids or [])
        ],
        last_login_at=user.last_login_at,
        created_at=user.created_at,
    )


@router.get("/audit-logs", response_model=List[AuditLogOut])
def list_org_audit_logs(
    limit: int = Query(default=100, ge=1, le=500),
    auth: AuthContext = Depends(require_permissions("org:view_audit", "org:manage_settings")),
    db: Session = Depends(get_db),
) -> List[AuditLogOut]:
    logs = (
        db.execute(
            select(AuditLog)
            .where(AuditLog.organization_id == auth.organization_id)
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return [AuditLogOut.model_validate(item) for item in logs]
