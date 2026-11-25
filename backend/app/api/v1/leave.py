from datetime import datetime, timezone
from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import (
    AuthContext,
    require_org_member,
    require_permissions,
)
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.models.employee import Employee
from app.models.organization import Department
from app.models.requests import LeaveRequest, LeaveType, Notification
from app.schemas.requests import (
    LeaveRequestCreate,
    LeaveRequestOut,
    LeaveRequestReview,
    LeaveTypeCreate,
    LeaveTypeOut,
)
from app.services.audit_service import record_audit_log

router = APIRouter(prefix="/leave", tags=["Leave Management"])


@router.get("/types", response_model=List[LeaveTypeOut])
def list_leave_types(
    auth: AuthContext = Depends(require_org_member),
    db: Session = Depends(get_db),
) -> List[LeaveTypeOut]:
    rows = (
        db.execute(
            select(LeaveType)
            .where(LeaveType.organization_id == auth.organization_id)
            .order_by(LeaveType.name)
        )
        .scalars()
        .all()
    )
    return [LeaveTypeOut.model_validate(lt) for lt in rows]


@router.post("/types", response_model=LeaveTypeOut, status_code=status.HTTP_201_CREATED)
def create_leave_type(
    payload: LeaveTypeCreate,
    auth: AuthContext = Depends(require_permissions("leave:manage_types")),
    db: Session = Depends(get_db),
) -> LeaveTypeOut:
    lt = LeaveType(
        organization_id=auth.organization_id,
        name=payload.name.strip(),
        code=payload.code.strip().upper(),
        is_paid=payload.is_paid,
        max_days_per_year=payload.max_days_per_year,
    )
    db.add(lt)
    db.commit()
    db.refresh(lt)
    return LeaveTypeOut.model_validate(lt)


@router.get("/requests", response_model=List[LeaveRequestOut])
def list_leave_requests(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    auth: AuthContext = Depends(require_org_member),
    db: Session = Depends(get_db),
) -> List[LeaveRequestOut]:
    query = select(LeaveRequest).where(
        LeaveRequest.organization_id == auth.organization_id
    )
    if (
        "leave:view_all" not in auth.permissions
        and "leave:view_department" not in auth.permissions
    ):
        emp = (
            db.execute(select(Employee).where(Employee.user_id == auth.user.id))
            .scalars()
            .first()
        )
        if not emp:
            return []
        query = query.where(LeaveRequest.employee_id == emp.id)
    elif "leave:view_all" not in auth.permissions:
        if not auth.assigned_department_ids:
            return []
        dept_emp_ids = [
            row[0]
            for row in db.execute(
                select(Employee.id).where(
                    Employee.organization_id == auth.organization_id,
                    Employee.department_id.in_(auth.assigned_department_ids),
                )
            ).all()
        ]
        if not dept_emp_ids:
            return []
        query = query.where(LeaveRequest.employee_id.in_(dept_emp_ids))

    if status_filter:
        query = query.where(LeaveRequest.status == status_filter)

    rows = db.execute(query.order_by(LeaveRequest.created_at.desc())).scalars().all()
    employees = {
        e.id: e
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
    leave_types = {
        lt.id: lt.name
        for lt in db.execute(
            select(LeaveType).where(LeaveType.organization_id == auth.organization_id)
        )
        .scalars()
        .all()
    }

    return [
        LeaveRequestOut(
            id=r.id,
            organization_id=r.organization_id,
            employee_id=r.employee_id,
            employee_name=f"{employees[r.employee_id].first_name} {employees[r.employee_id].last_name}"
            if r.employee_id in employees
            else "Unknown",
            employee_code=employees[r.employee_id].employee_code
            if r.employee_id in employees
            else "UNKNOWN",
            department_name=depts.get(employees[r.employee_id].department_id)
            if r.employee_id in employees and employees[r.employee_id].department_id
            else None,
            leave_type_id=r.leave_type_id,
            leave_type_name=leave_types.get(r.leave_type_id, "Leave"),
            start_date=r.start_date,
            end_date=r.end_date,
            reason=r.reason,
            status=r.status,
            reviewed_at=r.reviewed_at,
            reviewer_comment=r.reviewer_comment,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.post(
    "/requests",
    response_model=LeaveRequestOut,
    status_code=status.HTTP_201_CREATED,
)
def submit_leave_request(
    payload: LeaveRequestCreate,
    auth: AuthContext = Depends(require_permissions("leave:request")),
    db: Session = Depends(get_db),
) -> LeaveRequestOut:
    if payload.end_date < payload.start_date:
        raise ConflictError("End date cannot be earlier than start date")

    emp = (
        db.execute(
            select(Employee).where(
                Employee.organization_id == auth.organization_id,
                Employee.user_id == auth.user.id,
            )
        )
        .scalars()
        .first()
    )
    if not emp:
        raise NotFoundError("No employee profile linked to your user account")

    lt = db.get(LeaveType, payload.leave_type_id)
    if not lt or lt.organization_id != auth.organization_id:
        raise NotFoundError("Leave type not found")

    req = LeaveRequest(
        organization_id=auth.organization_id,
        employee_id=emp.id,
        leave_type_id=lt.id,
        start_date=payload.start_date,
        end_date=payload.end_date,
        reason=payload.reason.strip(),
        status="pending",
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    return LeaveRequestOut(
        id=req.id,
        organization_id=req.organization_id,
        employee_id=req.employee_id,
        employee_name=f"{emp.first_name} {emp.last_name}",
        employee_code=emp.employee_code,
        leave_type_id=lt.id,
        leave_type_name=lt.name,
        start_date=req.start_date,
        end_date=req.end_date,
        reason=req.reason,
        status=req.status,
        reviewed_at=req.reviewed_at,
        reviewer_comment=req.reviewer_comment,
        created_at=req.created_at,
    )


@router.patch("/requests/{request_id}/review", response_model=LeaveRequestOut)
def review_leave_request(
    request_id: uuid.UUID,
    payload: LeaveRequestReview,
    auth: AuthContext = Depends(require_permissions("leave:approve")),
    db: Session = Depends(get_db),
) -> LeaveRequestOut:
    req = db.get(LeaveRequest, request_id)
    if not req or req.organization_id != auth.organization_id:
        raise NotFoundError("Leave request not found")
    if req.status != "pending":
        raise ConflictError("Leave request has already been reviewed")

    emp = db.get(Employee, req.employee_id)
    if (
        "leave:view_all" not in auth.permissions
        and "department_manager" in auth.roles
    ):
        if not emp or not emp.department_id or emp.department_id not in auth.assigned_department_ids:
            raise ForbiddenError("You are not authorized to review this department's leave request")

    req.status = payload.status
    req.reviewed_by_user_id = auth.user.id
    req.reviewed_at = datetime.now(timezone.utc)
    req.reviewer_comment = payload.reviewer_comment

    if emp and emp.user_id:
        db.add(
            Notification(
                organization_id=auth.organization_id,
                user_id=emp.user_id,
                title=f"Leave request {payload.status}",
                message=f"Your leave request ({req.start_date} to {req.end_date}) was {payload.status}.",
                category="leave",
            )
        )

    record_audit_log(
        db,
        action=f"leave.{payload.status}",
        entity_type="leave_request",
        entity_id=str(req.id),
        organization_id=auth.organization_id,
        actor_user_id=auth.user.id,
        actor_email=auth.user.email,
        reason=payload.reviewer_comment,
    )
    db.commit()
    db.refresh(req)

    lt = db.get(LeaveType, req.leave_type_id)
    return LeaveRequestOut(
        id=req.id,
        organization_id=req.organization_id,
        employee_id=req.employee_id,
        employee_name=f"{emp.first_name} {emp.last_name}" if emp else "Unknown",
        employee_code=emp.employee_code if emp else "UNKNOWN",
        leave_type_id=req.leave_type_id,
        leave_type_name=lt.name if lt else "Leave",
        start_date=req.start_date,
        end_date=req.end_date,
        reason=req.reason,
        status=req.status,
        reviewed_at=req.reviewed_at,
        reviewer_comment=req.reviewer_comment,
        created_at=req.created_at,
    )
