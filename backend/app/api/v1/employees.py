import csv
from datetime import date
import io
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import AuthContext, require_permissions
from app.core.exceptions import ForbiddenError, NotFoundError
from app.core.security import hash_secret
from app.models.employee import Employee, EmployeeCredential
from app.models.organization import Department
from app.schemas.employee import (
    BulkImportPreviewResponse,
    EmployeeCreate,
    EmployeeListResponse,
    EmployeeOut,
    EmployeeUpdate,
)
from app.services.audit_service import record_audit_log
from app.services.employee_service import (
    create_employee,
    preview_csv_import,
    serialize_employee,
    validate_employee_org_refs,
)

router = APIRouter(prefix="/employees", tags=["Employees"])


@router.get("", response_model=EmployeeListResponse)
def list_employees(
    search: Optional[str] = Query(default=None),
    department_id: Optional[uuid.UUID] = Query(default=None),
    employment_status: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    auth: AuthContext = Depends(require_permissions("employee:read")),
    db: Session = Depends(get_db),
) -> EmployeeListResponse:
    query = select(Employee).where(Employee.organization_id == auth.organization_id)

    # Department managers without org-wide employee read are scoped to assigned departments
    if (
        "department_manager" in auth.roles
        and "org_admin" not in auth.roles
        and "hr_manager" not in auth.roles
    ):
        if not auth.assigned_department_ids:
            return EmployeeListResponse(items=[], total=0, page=page, page_size=page_size)
        query = query.where(Employee.department_id.in_(auth.assigned_department_ids))

    if search:
        like = f"%{search.strip()}%"
        query = query.where(
            or_(
                Employee.employee_code.ilike(like),
                Employee.first_name.ilike(like),
                Employee.last_name.ilike(like),
                Employee.phone_number.ilike(like),
                Employee.email.ilike(like),
            )
        )
    if department_id:
        query = query.where(Employee.department_id == department_id)
    if employment_status:
        query = query.where(Employee.employment_status == employment_status)

    total = db.execute(select(func.count()).select_from(query.subquery())).scalar_one()
    rows = (
        db.execute(
            query.order_by(Employee.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )

    return EmployeeListResponse(
        items=[serialize_employee(db, e) for e in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=EmployeeOut, status_code=status.HTTP_201_CREATED)
def register_employee(
    payload: EmployeeCreate,
    auth: AuthContext = Depends(require_permissions("employee:create")),
    db: Session = Depends(get_db),
) -> EmployeeOut:
    return create_employee(
        db,
        organization_id=auth.organization_id,
        payload=payload,
        actor_user_id=auth.user.id,
        actor_email=auth.user.email,
    )


@router.get("/import/template")
def download_import_template(
    _: AuthContext = Depends(require_permissions("employee:import")),
) -> Response:
    csv_content = (
        "employee_code,first_name,last_name,phone_number,email,department,employment_type,employment_start_date,pin\n"
        "EMP-1001,Abebe,Kebede,+251911000001,abebe@example.com,Operations,full_time,2026-01-15,4321\n"
    )
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=employee_import_template.csv"},
    )


@router.post("/import/preview", response_model=BulkImportPreviewResponse)
async def preview_employee_import(
    file: UploadFile = File(...),
    auth: AuthContext = Depends(require_permissions("employee:import")),
    db: Session = Depends(get_db),
) -> BulkImportPreviewResponse:
    raw = await file.read()
    text = raw.decode("utf-8-sig")
    return preview_csv_import(db, organization_id=auth.organization_id, csv_text=text)


@router.post("/import/confirm")
async def confirm_employee_import(
    file: UploadFile = File(...),
    auth: AuthContext = Depends(require_permissions("employee:import")),
    db: Session = Depends(get_db),
) -> dict:
    raw = await file.read()
    text = raw.decode("utf-8-sig")
    preview = preview_csv_import(db, organization_id=auth.organization_id, csv_text=text)
    if preview.error_count > 0:
        raise ForbiddenError(
            f"Cannot import CSV with {preview.error_count} validation errors. Fix all errors first."
        )

    dept_by_name = {
        d.name.lower(): d.id
        for d in db.execute(
            select(Department).where(Department.organization_id == auth.organization_id)
        )
        .scalars()
        .all()
    }

    reader = csv.DictReader(io.StringIO(text))
    imported_count = 0
    for row in reader:
        code = (row.get("employee_code") or "").strip()
        if not code:
            continue
        dept_name = (row.get("department") or "").strip().lower()
        dept_id = dept_by_name.get(dept_name) if dept_name else None
        payload = EmployeeCreate(
            employee_code=code,
            first_name=(row.get("first_name") or "").strip(),
            last_name=(row.get("last_name") or "").strip(),
            phone_number=(row.get("phone_number") or "").strip(),
            email=(row.get("email") or "").strip() or None,
            department_id=dept_id,
            employment_type=(row.get("employment_type") or "full_time").strip(),
            employment_start_date=date.fromisoformat(
                (row.get("employment_start_date") or "").strip()
            ),
            pin=(row.get("pin") or "").strip(),
        )
        create_employee(
            db,
            organization_id=auth.organization_id,
            payload=payload,
            actor_user_id=auth.user.id,
            actor_email=auth.user.email,
        )
        imported_count += 1

    return {"imported": imported_count}


@router.get("/{employee_id}", response_model=EmployeeOut)
def get_employee(
    employee_id: uuid.UUID,
    auth: AuthContext = Depends(require_permissions("employee:read")),
    db: Session = Depends(get_db),
) -> EmployeeOut:
    emp = db.get(Employee, employee_id)
    if not emp or emp.organization_id != auth.organization_id:
        raise NotFoundError("Employee not found")

    if (
        "department_manager" in auth.roles
        and "org_admin" not in auth.roles
        and "hr_manager" not in auth.roles
    ):
        if not emp.department_id or emp.department_id not in auth.assigned_department_ids:
            raise ForbiddenError("You are not authorized to view this employee")

    return serialize_employee(db, emp)


@router.patch("/{employee_id}", response_model=EmployeeOut)
def update_employee(
    employee_id: uuid.UUID,
    payload: EmployeeUpdate,
    auth: AuthContext = Depends(require_permissions("employee:update")),
    db: Session = Depends(get_db),
) -> EmployeeOut:
    emp = db.get(Employee, employee_id)
    if not emp or emp.organization_id != auth.organization_id:
        raise NotFoundError("Employee not found")

    data = payload.model_dump(exclude_unset=True)
    validate_employee_org_refs(
        db,
        organization_id=auth.organization_id,
        department_id=data.get("department_id"),
        position_id=data.get("position_id"),
        location_id=data.get("location_id"),
        supervisor_id=data.get("supervisor_id"),
    )
    new_pin = data.pop("new_pin", None)
    for field, val in data.items():
        setattr(emp, field, val)

    if new_pin:
        cred = (
            db.execute(
                select(EmployeeCredential).where(
                    EmployeeCredential.employee_id == emp.id
                )
            )
            .scalars()
            .first()
        )
        if cred:
            cred.pin_hash = hash_secret(new_pin)
            cred.failed_attempts = 0
            cred.locked_until = None

    record_audit_log(
        db,
        action="employee.updated",
        entity_type="employee",
        entity_id=str(emp.id),
        organization_id=auth.organization_id,
        actor_user_id=auth.user.id,
        actor_email=auth.user.email,
        metadata={"updated_fields": list(data.keys()) + (["pin"] if new_pin else [])},
    )
    db.commit()
    db.refresh(emp)
    return serialize_employee(db, emp)
