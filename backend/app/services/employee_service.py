import csv
from datetime import date
import io
from typing import List, Optional
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.core.security import hash_secret
from app.models.employee import Employee, EmployeeCredential
from app.models.organization import Department, Location, Position
from app.models.platform import Subscription, SubscriptionPlan
from app.models.user import User, UserRole
from app.schemas.employee import (
    BulkImportPreviewResponse,
    BulkImportPreviewRow,
    BulkImportRowError,
    EmployeeCreate,
    EmployeeOut,
)
from app.services.audit_service import record_audit_log
from app.services.rbac_service import get_org_role_by_code


def _check_employee_plan_limit(db: Session, organization_id: uuid.UUID) -> None:
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
        return
    plan = db.get(SubscriptionPlan, sub.plan_id)
    if not plan:
        return
    active_count = db.execute(
        select(func.count(Employee.id)).where(
            Employee.organization_id == organization_id,
            Employee.employment_status == "active",
        )
    ).scalar_one()
    if active_count >= plan.max_employees:
        raise ForbiddenError(
            f"Subscription plan '{plan.name}' limit of {plan.max_employees} active employees has been reached."
        )


def serialize_employee(db: Session, emp: Employee) -> EmployeeOut:
    dept = db.get(Department, emp.department_id) if emp.department_id else None
    pos = db.get(Position, emp.position_id) if emp.position_id else None
    loc = db.get(Location, emp.location_id) if emp.location_id else None
    return EmployeeOut(
        id=emp.id,
        organization_id=emp.organization_id,
        employee_code=emp.employee_code,
        user_id=emp.user_id,
        first_name=emp.first_name,
        last_name=emp.last_name,
        email=emp.email,
        phone_number=emp.phone_number,
        department_id=emp.department_id,
        department_name=dept.name if dept else None,
        position_id=emp.position_id,
        position_title=pos.title if pos else None,
        location_id=emp.location_id,
        location_name=loc.name if loc else None,
        supervisor_id=emp.supervisor_id,
        employment_type=emp.employment_type,
        employment_start_date=emp.employment_start_date,
        employment_status=emp.employment_status,
        notes=emp.notes,
        created_at=emp.created_at,
    )


def validate_employee_org_refs(
    db: Session,
    *,
    organization_id: uuid.UUID,
    department_id: Optional[uuid.UUID] = None,
    position_id: Optional[uuid.UUID] = None,
    location_id: Optional[uuid.UUID] = None,
    supervisor_id: Optional[uuid.UUID] = None,
) -> None:
    """Verify all referenced organizational entities belong to the same tenant."""
    if department_id is not None:
        dept = db.get(Department, department_id)
        if not dept or dept.organization_id != organization_id:
            raise NotFoundError("Selected department does not belong to this organization")

    if position_id is not None:
        pos = db.get(Position, position_id)
        if not pos or pos.organization_id != organization_id:
            raise NotFoundError("Selected position does not belong to this organization")

    if location_id is not None:
        loc = db.get(Location, location_id)
        if not loc or loc.organization_id != organization_id:
            raise NotFoundError("Selected location does not belong to this organization")

    if supervisor_id is not None:
        sup = db.get(Employee, supervisor_id)
        if not sup or sup.organization_id != organization_id:
            raise NotFoundError("Selected supervisor does not belong to this organization")


def create_employee(
    db: Session,
    *,
    organization_id: uuid.UUID,
    payload: EmployeeCreate,
    actor_user_id: uuid.UUID,
    actor_email: str,
) -> EmployeeOut:
    _check_employee_plan_limit(db, organization_id)

    existing_code = (
        db.execute(
            select(Employee).where(
                Employee.organization_id == organization_id,
                Employee.employee_code == payload.employee_code.strip(),
            )
        )
        .scalars()
        .first()
    )
    if existing_code:
        raise ConflictError(
            f"Employee ID '{payload.employee_code}' already exists in this organization."
        )

    validate_employee_org_refs(
        db,
        organization_id=organization_id,
        department_id=payload.department_id,
        position_id=payload.position_id,
        location_id=payload.location_id,
        supervisor_id=payload.supervisor_id,
    )

    user_id: Optional[uuid.UUID] = None
    if payload.create_user_account:
        if not payload.email:
            raise ConflictError("Email is required when creating an employee login account")
        existing_user = (
            db.execute(select(User).where(User.email == payload.email.lower().strip()))
            .scalars()
            .first()
        )
        if existing_user:
            raise ConflictError("A user account with this email already exists")

        raw_pw = payload.user_password or payload.pin + "Noram!2026"
        emp_user = User(
            organization_id=organization_id,
            email=payload.email.lower().strip(),
            full_name=f"{payload.first_name.strip()} {payload.last_name.strip()}",
            password_hash=hash_secret(raw_pw),
            is_platform_admin=False,
            is_active=True,
        )
        db.add(emp_user)
        db.flush()
        emp_role = get_org_role_by_code(db, organization_id, "employee")
        if emp_role:
            db.add(UserRole(user_id=emp_user.id, role_id=emp_role.id))
        user_id = emp_user.id

    emp = Employee(
        organization_id=organization_id,
        employee_code=payload.employee_code.strip(),
        user_id=user_id,
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        email=payload.email.lower().strip() if payload.email else None,
        phone_number=payload.phone_number.strip(),
        department_id=payload.department_id,
        position_id=payload.position_id,
        location_id=payload.location_id,
        supervisor_id=payload.supervisor_id,
        employment_type=payload.employment_type,
        employment_start_date=payload.employment_start_date,
        employment_status=payload.employment_status,
        notes=payload.notes,
    )
    db.add(emp)
    db.flush()

    cred = EmployeeCredential(
        organization_id=organization_id,
        employee_id=emp.id,
        pin_hash=hash_secret(payload.pin),
    )
    db.add(cred)

    record_audit_log(
        db,
        action="employee.created",
        entity_type="employee",
        entity_id=str(emp.id),
        organization_id=organization_id,
        actor_user_id=actor_user_id,
        actor_email=actor_email,
        metadata={"employee_code": emp.employee_code},
    )
    db.commit()
    db.refresh(emp)
    return serialize_employee(db, emp)


def preview_csv_import(
    db: Session, *, organization_id: uuid.UUID, csv_text: str
) -> BulkImportPreviewResponse:
    reader = csv.DictReader(io.StringIO(csv_text))
    existing_codes = {
        row[0]
        for row in db.execute(
            select(Employee.employee_code).where(
                Employee.organization_id == organization_id
            )
        ).all()
    }
    seen_in_file: set[str] = set()
    valid_rows: List[BulkImportPreviewRow] = []
    errors: List[BulkImportRowError] = []

    for idx, row in enumerate(reader, start=2):
        code = (row.get("employee_code") or "").strip()
        first = (row.get("first_name") or "").strip()
        last = (row.get("last_name") or "").strip()
        phone = (row.get("phone_number") or "").strip()
        pin = (row.get("pin") or "").strip()
        start_raw = (row.get("employment_start_date") or "").strip()
        emp_type = (row.get("employment_type") or "full_time").strip()

        if not code or not first or not last or not phone or not pin or not start_raw:
            errors.append(
                BulkImportRowError(
                    row_number=idx,
                    employee_code=code or None,
                    error="Missing required fields (employee_code, first_name, last_name, phone_number, employment_start_date, pin)",
                )
            )
            continue
        if not pin.isdigit() or len(pin) < 4:
            errors.append(
                BulkImportRowError(
                    row_number=idx,
                    employee_code=code,
                    error="PIN must be numeric and at least 4 digits",
                )
            )
            continue
        if code in existing_codes or code in seen_in_file:
            errors.append(
                BulkImportRowError(
                    row_number=idx,
                    employee_code=code,
                    error="Duplicate employee_code",
                )
            )
            continue
        try:
            start_dt = date.fromisoformat(start_raw)
        except ValueError:
            errors.append(
                BulkImportRowError(
                    row_number=idx,
                    employee_code=code,
                    error="Invalid employment_start_date (use YYYY-MM-DD)",
                )
            )
            continue

        seen_in_file.add(code)
        valid_rows.append(
            BulkImportPreviewRow(
                row_number=idx,
                employee_code=code,
                first_name=first,
                last_name=last,
                phone_number=phone,
                email=(row.get("email") or "").strip() or None,
                department_name=(row.get("department") or "").strip() or None,
                employment_type=emp_type
                if emp_type in {"full_time", "part_time", "contract", "temporary"}
                else "full_time",
                employment_start_date=start_dt,
            )
        )

    return BulkImportPreviewResponse(
        valid_count=len(valid_rows),
        error_count=len(errors),
        valid_rows=valid_rows,
        errors=errors,
    )
