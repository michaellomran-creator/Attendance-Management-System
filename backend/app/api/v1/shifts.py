from typing import List
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import (
    AuthContext,
    require_org_member,
    require_permissions,
)
from app.core.exceptions import ConflictError, NotFoundError
from app.models.employee import Employee
from app.models.organization import Department
from app.models.shift import Holiday, Shift, ShiftAssignment, ShiftPolicy
from app.schemas.shift import (
    HolidayCreate,
    HolidayOut,
    ShiftAssignmentCreate,
    ShiftAssignmentOut,
    ShiftCreate,
    ShiftOut,
    ShiftUpdate,
)
from app.services.audit_service import record_audit_log

router = APIRouter(prefix="/shifts", tags=["Shifts & Schedules"])


@router.get("", response_model=List[ShiftOut])
def list_shifts(
    auth: AuthContext = Depends(require_org_member),
    db: Session = Depends(get_db),
) -> List[ShiftOut]:
    rows = (
        db.execute(
            select(Shift)
            .where(Shift.organization_id == auth.organization_id)
            .order_by(Shift.name)
        )
        .scalars()
        .all()
    )
    return [ShiftOut.model_validate(s) for s in rows]


@router.post("", response_model=ShiftOut, status_code=status.HTTP_201_CREATED)
def create_shift(
    payload: ShiftCreate,
    auth: AuthContext = Depends(require_permissions("shift:manage")),
    db: Session = Depends(get_db),
) -> ShiftOut:
    crosses = payload.crosses_midnight or (payload.end_time <= payload.start_time)
    shift = Shift(
        organization_id=auth.organization_id,
        name=payload.name.strip(),
        shift_type=payload.shift_type,
        start_time=payload.start_time,
        end_time=payload.end_time,
        crosses_midnight=crosses,
        applicable_days=payload.applicable_days,
        break_duration_minutes=payload.break_duration_minutes,
        grace_period_minutes=payload.grace_period_minutes,
        expected_work_minutes=payload.expected_work_minutes,
        minimum_work_minutes=payload.minimum_work_minutes,
        early_departure_threshold_minutes=payload.early_departure_threshold_minutes,
        overtime_threshold_minutes=payload.overtime_threshold_minutes,
    )
    db.add(shift)
    db.flush()

    pol = payload.policy
    db.add(
        ShiftPolicy(
            organization_id=auth.organization_id,
            shift_id=shift.id,
            overtime_eligible=pol.overtime_eligible if pol else True,
            overtime_requires_approval=pol.overtime_requires_approval if pol else True,
            auto_deduct_break=pol.auto_deduct_break if pol else False,
            mark_absent_after_minutes=pol.mark_absent_after_minutes if pol else 120,
        )
    )
    record_audit_log(
        db,
        action="shift.created",
        entity_type="shift",
        entity_id=str(shift.id),
        organization_id=auth.organization_id,
        actor_user_id=auth.user.id,
        actor_email=auth.user.email,
        metadata={"name": shift.name, "crosses_midnight": crosses},
    )
    db.commit()
    db.refresh(shift)
    return ShiftOut.model_validate(shift)


@router.patch("/{shift_id}", response_model=ShiftOut)
def update_shift(
    shift_id: uuid.UUID,
    payload: ShiftUpdate,
    auth: AuthContext = Depends(require_permissions("shift:manage")),
    db: Session = Depends(get_db),
) -> ShiftOut:
    shift = db.get(Shift, shift_id)
    if not shift or shift.organization_id != auth.organization_id:
        raise NotFoundError("Shift not found")

    data = payload.model_dump(exclude_unset=True)
    pol_data = data.pop("policy", None)
    for field, val in data.items():
        setattr(shift, field, val)

    if pol_data is not None:
        pol = (
            db.execute(select(ShiftPolicy).where(ShiftPolicy.shift_id == shift.id))
            .scalars()
            .first()
        )
        if pol:
            for field, val in pol_data.items():
                setattr(pol, field, val)

    record_audit_log(
        db,
        action="shift.updated",
        entity_type="shift",
        entity_id=str(shift.id),
        organization_id=auth.organization_id,
        actor_user_id=auth.user.id,
        actor_email=auth.user.email,
    )
    db.commit()
    db.refresh(shift)
    return ShiftOut.model_validate(shift)


@router.get("/assignments", response_model=List[ShiftAssignmentOut])
def list_shift_assignments(
    auth: AuthContext = Depends(require_org_member),
    db: Session = Depends(get_db),
) -> List[ShiftAssignmentOut]:
    query = select(ShiftAssignment).where(
        ShiftAssignment.organization_id == auth.organization_id
    )
    if "employee" in auth.roles and "org_admin" not in auth.roles and "hr_manager" not in auth.roles:
        emp = (
            db.execute(select(Employee).where(Employee.user_id == auth.user.id))
            .scalars()
            .first()
        )
        if emp:
            query = query.where(
                (ShiftAssignment.employee_id == emp.id)
                | (ShiftAssignment.department_id == emp.department_id)
            )

    rows = db.execute(query.order_by(ShiftAssignment.effective_from.desc())).scalars().all()
    shifts = {
        s.id: s.name
        for s in db.execute(
            select(Shift).where(Shift.organization_id == auth.organization_id)
        )
        .scalars()
        .all()
    }
    employees = {
        e.id: f"{e.first_name} {e.last_name}"
        for e in db.execute(
            select(Employee).where(Employee.organization_id == auth.organization_id)
        )
        .scalars()
        .all()
    }
    depts = {
        d.id: d.name
        for d in db.execute(
            select(Department).where(Department.organization_id == auth.organization_id)
        )
        .scalars()
        .all()
    }
    return [
        ShiftAssignmentOut(
            id=a.id,
            organization_id=a.organization_id,
            shift_id=a.shift_id,
            shift_name=shifts.get(a.shift_id),
            employee_id=a.employee_id,
            employee_name=employees.get(a.employee_id) if a.employee_id else None,
            department_id=a.department_id,
            department_name=depts.get(a.department_id) if a.department_id else None,
            effective_from=a.effective_from,
            effective_to=a.effective_to,
            is_temporary=a.is_temporary,
            rotation_group=a.rotation_group,
            created_at=a.created_at,
        )
        for a in rows
    ]


@router.post(
    "/assignments",
    response_model=ShiftAssignmentOut,
    status_code=status.HTTP_201_CREATED,
)
def assign_shift(
    payload: ShiftAssignmentCreate,
    auth: AuthContext = Depends(require_permissions("shift:assign")),
    db: Session = Depends(get_db),
) -> ShiftAssignmentOut:
    if not payload.employee_id and not payload.department_id:
        raise ConflictError("Either employee_id or department_id must be provided")

    shift = db.get(Shift, payload.shift_id)
    if not shift or shift.organization_id != auth.organization_id:
        raise NotFoundError("Shift not found")

    if payload.employee_id:
        emp = db.get(Employee, payload.employee_id)
        if not emp or emp.organization_id != auth.organization_id:
            raise NotFoundError("Employee not found")

    if payload.department_id:
        dept = db.get(Department, payload.department_id)
        if not dept or dept.organization_id != auth.organization_id:
            raise NotFoundError("Department not found")

    assignment = ShiftAssignment(
        organization_id=auth.organization_id,
        shift_id=payload.shift_id,
        employee_id=payload.employee_id,
        department_id=payload.department_id,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
        is_temporary=payload.is_temporary,
        rotation_group=payload.rotation_group,
    )
    db.add(assignment)
    record_audit_log(
        db,
        action="shift.assigned",
        entity_type="shift_assignment",
        entity_id=str(shift.id),
        organization_id=auth.organization_id,
        actor_user_id=auth.user.id,
        actor_email=auth.user.email,
    )
    db.commit()
    db.refresh(assignment)

    return ShiftAssignmentOut(
        id=assignment.id,
        organization_id=assignment.organization_id,
        shift_id=assignment.shift_id,
        shift_name=shift.name,
        employee_id=assignment.employee_id,
        department_id=assignment.department_id,
        effective_from=assignment.effective_from,
        effective_to=assignment.effective_to,
        is_temporary=assignment.is_temporary,
        rotation_group=assignment.rotation_group,
        created_at=assignment.created_at,
    )


@router.get("/holidays", response_model=List[HolidayOut])
def list_holidays(
    auth: AuthContext = Depends(require_org_member),
    db: Session = Depends(get_db),
) -> List[HolidayOut]:
    rows = (
        db.execute(
            select(Holiday)
            .where(Holiday.organization_id == auth.organization_id)
            .order_by(Holiday.holiday_date)
        )
        .scalars()
        .all()
    )
    return [HolidayOut.model_validate(h) for h in rows]


@router.post("/holidays", response_model=HolidayOut, status_code=status.HTTP_201_CREATED)
def create_holiday(
    payload: HolidayCreate,
    auth: AuthContext = Depends(require_permissions("shift:manage")),
    db: Session = Depends(get_db),
) -> HolidayOut:
    h = Holiday(
        organization_id=auth.organization_id,
        name=payload.name.strip(),
        holiday_date=payload.holiday_date,
        is_paid=payload.is_paid,
    )
    db.add(h)
    db.commit()
    db.refresh(h)
    return HolidayOut.model_validate(h)
