from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional, Set
import uuid

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_token, hash_token
from app.models.attendance import AttendanceTerminal
from app.models.organization import Organization
from app.models.platform import Subscription
from app.models.user import Role, RolePermission, User, UserRole

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class AuthContext:
    user: User
    organization_id: Optional[uuid.UUID]
    roles: Set[str]
    permissions: Set[str]
    is_platform_admin: bool
    assigned_department_ids: Set[uuid.UUID]


def _ensure_org_and_subscription_active(db: Session, organization_id: uuid.UUID) -> None:
    org = db.get(Organization, organization_id)
    if not org or org.status != "active":
        raise ForbiddenError("Organization account is suspended or inactive")

    sub = (
        db.execute(
            select(Subscription)
            .where(Subscription.organization_id == organization_id)
            .order_by(Subscription.created_at.desc())
        )
        .scalars()
        .first()
    )
    if sub:
        if sub.status in {"suspended", "cancelled"}:
            raise ForbiddenError("Organization subscription is suspended or cancelled")
        today = datetime.now(timezone.utc).date()
        grace_deadline = sub.expiry_date + timedelta(days=sub.grace_period_days)
        if sub.status == "expired" and today > grace_deadline:
            raise ForbiddenError("Organization subscription has expired beyond grace period")


def get_current_auth(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> AuthContext:
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError("Missing authentication token")

    payload = decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        raise UnauthorizedError("Invalid or expired authentication token")

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise UnauthorizedError("Invalid authentication subject")

    user = (
        db.execute(
            select(User)
            .options(
                selectinload(User.user_roles)
                .selectinload(UserRole.role)
                .selectinload(Role.permissions)
                .selectinload(RolePermission.permission)
            )
            .where(User.id == user_id)
        )
        .scalars()
        .first()
    )
    if not user or not user.is_active:
        raise UnauthorizedError("User account is inactive or does not exist")

    # Verify organization and subscription are active for non-platform users
    if user.organization_id is not None:
        _ensure_org_and_subscription_active(db, user.organization_id)

    role_codes: Set[str] = set()
    permission_codes: Set[str] = set()
    for ur in user.user_roles:
        if ur.role:
            role_codes.add(ur.role.code)
            for rp in ur.role.permissions:
                if rp.permission:
                    permission_codes.add(rp.permission.code)

    dept_ids: Set[uuid.UUID] = set()
    for raw_id in user.assigned_department_ids or []:
        try:
            dept_ids.add(uuid.UUID(str(raw_id)))
        except ValueError:
            continue

    return AuthContext(
        user=user,
        organization_id=user.organization_id,
        roles=role_codes,
        permissions=permission_codes,
        is_platform_admin=user.is_platform_admin,
        assigned_department_ids=dept_ids,
    )


def require_platform_admin(
    auth: AuthContext = Depends(get_current_auth),
) -> AuthContext:
    if not auth.is_platform_admin:
        raise ForbiddenError("Platform administrator privileges required")
    return auth


def require_org_member(
    auth: AuthContext = Depends(get_current_auth),
) -> AuthContext:
    """Ensure the authenticated user belongs to an organization (tenant isolation)."""
    if auth.organization_id is None:
        raise ForbiddenError("Organization membership is required for this resource")
    return auth


def require_permissions(*required: str) -> Callable[[AuthContext], AuthContext]:
    is_platform_only = all(p.startswith("platform:") for p in required)

    def dependency(auth: AuthContext = Depends(get_current_auth)) -> AuthContext:
        if auth.is_platform_admin and is_platform_only:
            return auth
        if not is_platform_only and auth.organization_id is None:
            raise ForbiddenError("Organization membership is required for this resource")
        if not any(p in auth.permissions for p in required):
            raise ForbiddenError(
                f"Missing required permission: {', '.join(required)}"
            )
        return auth

    return dependency


def get_authenticated_terminal(
    x_terminal_token: Optional[str] = Header(default=None, alias="X-Terminal-Token"),
    db: Session = Depends(get_db),
) -> AttendanceTerminal:
    if not x_terminal_token:
        raise UnauthorizedError("Terminal authentication token is required")

    token_digest = hash_token(x_terminal_token)
    terminal = (
        db.execute(
            select(AttendanceTerminal).where(
                AttendanceTerminal.token_hash == token_digest
            )
        )
        .scalars()
        .first()
    )
    if not terminal or not terminal.is_active:
        raise UnauthorizedError("Terminal is unauthorized or deactivated")

    _ensure_org_and_subscription_active(db, terminal.organization_id)

    return terminal


def get_client_ip(request: Request) -> Optional[str]:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None
