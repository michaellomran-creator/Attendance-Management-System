from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.exceptions import ForbiddenError, TooManyRequestsError, UnauthorizedError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_secret,
    hash_token,
    rate_limiter,
    verify_secret,
)
from app.models.employee import Employee
from app.models.organization import Organization
from app.models.user import RefreshToken, Role, RolePermission, User, UserRole
from app.schemas.auth import TokenResponse, UserProfileResponse
from app.services.audit_service import record_audit_log


def build_user_profile(db: Session, user: User) -> UserProfileResponse:
    role_codes: list[str] = []
    permission_codes: set[str] = set()
    for ur in user.user_roles:
        if ur.role:
            role_codes.append(ur.role.code)
            for rp in ur.role.permissions:
                if rp.permission:
                    permission_codes.add(rp.permission.code)

    org_name: Optional[str] = None
    org_tz: Optional[str] = None
    if user.organization_id:
        org = db.get(Organization, user.organization_id)
        if org:
            org_name = org.name
            org_tz = org.timezone

    emp = (
        db.execute(select(Employee).where(Employee.user_id == user.id))
        .scalars()
        .first()
    )

    dept_ids: list[uuid.UUID] = []
    for raw_id in user.assigned_department_ids or []:
        try:
            dept_ids.append(uuid.UUID(str(raw_id)))
        except ValueError:
            continue

    return UserProfileResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        organization_id=user.organization_id,
        organization_name=org_name,
        organization_timezone=org_tz,
        is_platform_admin=user.is_platform_admin,
        roles=sorted(role_codes),
        permissions=sorted(permission_codes),
        assigned_department_ids=dept_ids,
        employee_id=emp.id if emp else None,
        employee_code=emp.employee_code if emp else None,
        must_change_password=user.must_change_password,
        last_login_at=user.last_login_at,
    )


def authenticate_user(
    db: Session,
    *,
    email: str,
    password: str,
    ip_address: Optional[str] = None,
) -> TokenResponse:
    rate_key = f"login:{email.lower()}:{ip_address or 'unknown'}"
    if not rate_limiter.check_and_record(
        rate_key, settings.LOGIN_RATE_LIMIT_PER_MINUTE, 60
    ):
        raise TooManyRequestsError(
            "Too many login attempts. Please wait a minute and try again."
        )

    user = (
        db.execute(
            select(User)
            .options(
                selectinload(User.user_roles)
                .selectinload(UserRole.role)
                .selectinload(Role.permissions)
                .selectinload(RolePermission.permission)
            )
            .where(User.email == email.lower().strip())
        )
        .scalars()
        .first()
    )

    if not user or not verify_secret(password, user.password_hash):
        record_audit_log(
            db,
            action="auth.login_failed",
            entity_type="user",
            actor_email=email.lower().strip(),
            organization_id=user.organization_id if user else None,
            ip_address=ip_address,
        )
        db.commit()
        raise UnauthorizedError("Invalid email or password")

    if not user.is_active:
        raise ForbiddenError("Your user account is inactive")

    if user.organization_id is not None:
        org = db.get(Organization, user.organization_id)
        if not org or org.status != "active":
            raise ForbiddenError("Your organization account is suspended or inactive")

    user.last_login_at = datetime.now(timezone.utc)
    rate_limiter.reset(rate_key)

    access_token = create_access_token(
        str(user.id),
        extra_claims={
            "org_id": str(user.organization_id) if user.organization_id else None,
            "is_platform_admin": user.is_platform_admin,
        },
    )
    raw_refresh = create_refresh_token(str(user.id))
    refresh_row = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw_refresh),
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    db.add(refresh_row)

    record_audit_log(
        db,
        action="auth.login_success",
        entity_type="user",
        entity_id=str(user.id),
        organization_id=user.organization_id,
        actor_user_id=user.id,
        actor_email=user.email,
        ip_address=ip_address,
    )
    db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=build_user_profile(db, user),
    )


def refresh_access_token(db: Session, raw_refresh_token: str) -> TokenResponse:
    payload = decode_token(raw_refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise UnauthorizedError("Invalid refresh token")

    token_digest = hash_token(raw_refresh_token)
    stored = (
        db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_digest)
        )
        .scalars()
        .first()
    )
    now = datetime.now(timezone.utc)
    if not stored or stored.revoked_at is not None or stored.expires_at < now:
        raise UnauthorizedError("Refresh token is expired or revoked")

    user = (
        db.execute(
            select(User)
            .options(
                selectinload(User.user_roles)
                .selectinload(UserRole.role)
                .selectinload(Role.permissions)
                .selectinload(RolePermission.permission)
            )
            .where(User.id == stored.user_id)
        )
        .scalars()
        .first()
    )
    if not user or not user.is_active:
        raise UnauthorizedError("User account is inactive")

    stored.revoked_at = now
    new_refresh = create_refresh_token(str(user.id))
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(new_refresh),
            expires_at=now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    access_token = create_access_token(
        str(user.id),
        extra_claims={
            "org_id": str(user.organization_id) if user.organization_id else None,
            "is_platform_admin": user.is_platform_admin,
        },
    )
    db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=build_user_profile(db, user),
    )


def change_user_password(
    db: Session, user: User, current_password: str, new_password: str
) -> None:
    if not verify_secret(current_password, user.password_hash):
        raise UnauthorizedError("Current password is incorrect")
    user.password_hash = hash_secret(new_password)
    user.must_change_password = False
    record_audit_log(
        db,
        action="auth.password_changed",
        entity_type="user",
        entity_id=str(user.id),
        organization_id=user.organization_id,
        actor_user_id=user.id,
        actor_email=user.email,
    )
    db.commit()
