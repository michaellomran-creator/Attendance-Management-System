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
from app.models.attendance import AttendanceEvent, AttendanceSession
from app.models.employee import Employee
from app.models.requests import AttendanceCorrectionRequest, Notification
from app.schemas.requests import (
    CorrectionRequestCreate,
    CorrectionRequestOut,
    CorrectionRequestReview,
)
from app.services.attendance_service import _upsert_daily_summary
from app.services.audit_service import record_audit_log

router = APIRouter(prefix="/corrections", tags=["Attendance Corrections"])


@router.get("", response_model=List[CorrectionRequestOut])
def list_correction_requests(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    auth: AuthContext = Depends(require_org_member),
    db: Session = Depends(get_db),
) -> List[CorrectionRequestOut]:
    query = select(AttendanceCorrectionRequest).where(
        AttendanceCorrectionRequest.organization_id == auth.organization_id
    )
    if (
        "attendance:view_all" not in auth.permissions
        and "attendance:view_department" not in auth.permissions
    ):
        emp = (
            db.execute(select(Employee).where(Employee.user_id == auth.user.id))
            .scalars()
            .first()
        )
        if not emp:
            return []
        query = query.where(AttendanceCorrectionRequest.employee_id == emp.id)
    elif "attendance:view_all" not in auth.permissions:
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
        query = query.where(AttendanceCorrectionRequest.employee_id.in_(dept_emp_ids))

    if status_filter:
        query = query.where(AttendanceCorrectionRequest.status == status_filter)

    rows = (
        db.execute(query.order_by(AttendanceCorrectionRequest.created_at.desc()))
        .scalars()
        .all()
    )
    employees = {
        e.id: e
        for e in db.execute(
            select(Employee).where(Employee.organization_id == auth.organization_id)
        )
        .scalars()
        .all()
    }
    return [
        CorrectionRequestOut(
            id=r.id,
            organization_id=r.organization_id,
            employee_id=r.employee_id,
            employee_name=f"{employees[r.employee_id].first_name} {employees[r.employee_id].last_name}"
            if r.employee_id in employees
            else "Unknown",
            employee_code=employees[r.employee_id].employee_code
            if r.employee_id in employees
            else "UNKNOWN",
            session_id=r.session_id,
            target_date=r.target_date,
            correction_type=r.correction_type,
            requested_check_in_at=r.requested_check_in_at,
            requested_check_out_at=r.requested_check_out_at,
            original_snapshot=r.original_snapshot,
            reason=r.reason,
            status=r.status,
            reviewed_at=r.reviewed_at,
            reviewer_comment=r.reviewer_comment,
            created_at=r.created_at,
        )
        for r in rows
    ]


@router.post(
    "",
    response_model=CorrectionRequestOut,
    status_code=status.HTTP_201_CREATED,
)
def submit_correction_request(
    payload: CorrectionRequestCreate,
    auth: AuthContext = Depends(require_permissions("attendance:correct_request")),
    db: Session = Depends(get_db),
) -> CorrectionRequestOut:
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

    snapshot = {}
    if payload.session_id:
        session = db.get(AttendanceSession, payload.session_id)
        if not session or session.organization_id != auth.organization_id:
            raise NotFoundError("Attendance session not found")
        if session.employee_id != emp.id:
            raise ForbiddenError("Cannot request correction for another employee's session")
        snapshot = {
            "check_in_at": session.check_in_at.isoformat(),
            "check_out_at": session.check_out_at.isoformat() if session.check_out_at else None,
            "status": session.status,
        }

    req = AttendanceCorrectionRequest(
        organization_id=auth.organization_id,
        employee_id=emp.id,
        session_id=payload.session_id,
        target_date=payload.target_date,
        correction_type=payload.correction_type,
        requested_check_in_at=payload.requested_check_in_at,
        requested_check_out_at=payload.requested_check_out_at,
        original_snapshot=snapshot,
        reason=payload.reason.strip(),
        status="pending",
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    return CorrectionRequestOut(
        id=req.id,
        organization_id=req.organization_id,
        employee_id=req.employee_id,
        employee_name=f"{emp.first_name} {emp.last_name}",
        employee_code=emp.employee_code,
        session_id=req.session_id,
        target_date=req.target_date,
        correction_type=req.correction_type,
        requested_check_in_at=req.requested_check_in_at,
        requested_check_out_at=req.requested_check_out_at,
        original_snapshot=req.original_snapshot,
        reason=req.reason,
        status=req.status,
        reviewed_at=req.reviewed_at,
        reviewer_comment=req.reviewer_comment,
        created_at=req.created_at,
    )


@router.patch("/{request_id}/review", response_model=CorrectionRequestOut)
def review_correction_request(
    request_id: uuid.UUID,
    payload: CorrectionRequestReview,
    auth: AuthContext = Depends(require_permissions("attendance:correct_approve")),
    db: Session = Depends(get_db),
) -> CorrectionRequestOut:
    req = db.get(AttendanceCorrectionRequest, request_id)
    if not req or req.organization_id != auth.organization_id:
        raise NotFoundError("Correction request not found")
    if req.status != "pending":
        raise ConflictError("Correction request has already been reviewed")

    emp = db.get(Employee, req.employee_id)
    if (
        "attendance:view_all" not in auth.permissions
        and "department_manager" in auth.roles
    ):
        if not emp or not emp.department_id or emp.department_id not in auth.assigned_department_ids:
            raise ForbiddenError("Not authorized to review corrections for this department")

    now = datetime.now(timezone.utc)
    req.status = payload.status
    req.reviewed_by_user_id = auth.user.id
    req.reviewed_at = now
    req.reviewer_comment = payload.reviewer_comment

    if payload.status == "approved":
        if req.session_id:
            session = db.get(AttendanceSession, req.session_id)
            if session:
                if req.requested_check_in_at:
                    session.check_in_at = req.requested_check_in_at
                if req.requested_check_out_at:
                    session.check_out_at = req.requested_check_out_at
                    session.is_open = False
                if session.check_out_at:
                    gross = max(
                        0,
                        int((session.check_out_at - session.check_in_at).total_seconds() // 60),
                    )
                    session.gross_minutes = gross
                    session.net_minutes = max(0, gross - session.break_minutes)
                    session.status = "present"
                db.add(
                    AttendanceEvent(
                        organization_id=auth.organization_id,
                        session_id=session.id,
                        employee_id=req.employee_id,
                        event_type="correction",
                        event_timestamp=now,
                        source="admin_correction",
                        metadata_json={
                            "correction_request_id": str(req.id),
                            "original_snapshot": req.original_snapshot,
                            "reason": req.reason,
                            "reviewer_comment": payload.reviewer_comment,
                        },
                    )
                )
        elif req.requested_check_in_at:
            check_out = req.requested_check_out_at
            gross = (
                max(0, int((check_out - req.requested_check_in_at).total_seconds() // 60))
                if check_out
                else 0
            )
            new_session = AttendanceSession(
                organization_id=auth.organization_id,
                employee_id=req.employee_id,
                work_date=req.target_date,
                check_in_at=req.requested_check_in_at,
                check_out_at=check_out,
                status="present" if check_out else "incomplete",
                is_open=check_out is None,
                gross_minutes=gross,
                net_minutes=gross,
                notes=f"Created via approved correction {req.id}",
            )
            db.add(new_session)
            db.flush()
            db.add(
                AttendanceEvent(
                    organization_id=auth.organization_id,
                    session_id=new_session.id,
                    employee_id=req.employee_id,
                    event_type="correction",
                    event_timestamp=now,
                    source="admin_correction",
                    metadata_json={
                        "correction_request_id": str(req.id),
                        "reason": req.reason,
                    },
                )
            )
        _upsert_daily_summary(
            db,
            organization_id=auth.organization_id,
            employee_id=req.employee_id,
            summary_date=req.target_date,
        )

    if emp and emp.user_id:
        db.add(
            Notification(
                organization_id=auth.organization_id,
                user_id=emp.user_id,
                title=f"Correction request {payload.status}",
                message=f"Your attendance correction for {req.target_date} was {payload.status}.",
                category="correction",
            )
        )

    record_audit_log(
        db,
        action=f"attendance_correction.{payload.status}",
        entity_type="attendance_correction_request",
        entity_id=str(req.id),
        organization_id=auth.organization_id,
        actor_user_id=auth.user.id,
        actor_email=auth.user.email,
        reason=payload.reviewer_comment,
        metadata={"original_snapshot": req.original_snapshot},
    )
    db.commit()
    db.refresh(req)

    return CorrectionRequestOut(
        id=req.id,
        organization_id=req.organization_id,
        employee_id=req.employee_id,
        employee_name=f"{emp.first_name} {emp.last_name}" if emp else "Unknown",
        employee_code=emp.employee_code if emp else "UNKNOWN",
        session_id=req.session_id,
        target_date=req.target_date,
        correction_type=req.correction_type,
        requested_check_in_at=req.requested_check_in_at,
        requested_check_out_at=req.requested_check_out_at,
        original_snapshot=req.original_snapshot,
        reason=req.reason,
        status=req.status,
        reviewed_at=req.reviewed_at,
        reviewer_comment=req.reviewer_comment,
        created_at=req.created_at,
    )
