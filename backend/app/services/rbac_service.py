from typing import Dict, Optional
import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import ALL_PERMISSIONS, ROLE_PERMISSION_MAP
from app.models.user import Permission, Role, RolePermission


def ensure_permissions_seeded(db: Session) -> Dict[str, Permission]:
    existing = {
        p.code: p for p in db.execute(select(Permission)).scalars().all()
    }
    for code, name, category in ALL_PERMISSIONS:
        if code not in existing:
            perm = Permission(code=code, name=name, category=category)
            db.add(perm)
            db.flush()
            existing[code] = perm
    return existing


def ensure_platform_roles(db: Session) -> Role:
    perms = ensure_permissions_seeded(db)
    role = (
        db.execute(
            select(Role).where(
                Role.organization_id.is_(None), Role.code == "platform_owner"
            )
        )
        .scalars()
        .first()
    )
    if not role:
        role = Role(
            organization_id=None,
            code="platform_owner",
            name="Platform Owner",
            scope="platform",
            is_system=True,
        )
        db.add(role)
        db.flush()
        for perm_code in ROLE_PERMISSION_MAP["platform_owner"]:
            if perm_code in perms:
                db.add(RolePermission(role_id=role.id, permission_id=perms[perm_code].id))
        db.flush()
    return role


def initialize_organization_roles(
    db: Session, organization_id: uuid.UUID
) -> Dict[str, Role]:
    perms = ensure_permissions_seeded(db)
    role_names = {
        "org_admin": "Organization Administrator",
        "hr_manager": "HR Manager",
        "department_manager": "Department Manager",
        "employee": "Employee",
    }
    created: Dict[str, Role] = {}
    for code, name in role_names.items():
        existing_role = (
            db.execute(
                select(Role).where(
                    Role.organization_id == organization_id, Role.code == code
                )
            )
            .scalars()
            .first()
        )
        if existing_role:
            created[code] = existing_role
            continue
        role = Role(
            organization_id=organization_id,
            code=code,
            name=name,
            scope="organization",
            is_system=True,
        )
        db.add(role)
        db.flush()
        for perm_code in ROLE_PERMISSION_MAP[code]:
            if perm_code in perms:
                db.add(RolePermission(role_id=role.id, permission_id=perms[perm_code].id))
        created[code] = role
    db.flush()
    return created


def get_org_role_by_code(
    db: Session, organization_id: uuid.UUID, role_code: str
) -> Optional[Role]:
    return (
        db.execute(
            select(Role).where(
                Role.organization_id == organization_id, Role.code == role_code
            )
        )
        .scalars()
        .first()
    )
