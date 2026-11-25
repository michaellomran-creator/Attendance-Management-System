from datetime import date, datetime, timedelta, timezone
from typing import List, Optional
import uuid
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import (
    AuthContext,
    require_org_member,
    require_permissions,
)
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.attendance import AttendanceSession, BreakRecord
from app.models.employee import Employee
from app.models.organization import Department, Location, Organization
from app.models.requests import LeaveRequest
from app.models.shift import Shift
from app.schemas.attendance import (
    AttendanceSessionOut,
    DashboardMetricsOut,
    TerminalPunchResponse,
)
from app.services.attendance_service import (
    end_employee_break,
    perform_check_in,
    perform_check_out,
    start_employee_break,
)

router = APIRouter(prefix="/attendance", tags=["Attendance"])


def _serialize_session(
    s: AttendanceSession,
    employees: dict[uuid.UUID, Employee],
    departments: dict[uuid.UUID, str],
    shifts: dict[uuid.UUID, str],
    locations: dict[uuid.UUID, str],
) -> AttendanceSessionOut:
    emp = employees.get(s.employee_id)
    return AttendanceSessionOut(
        id=s.id,
        organization_id=s.organization_id,
        employee_id=s.employee_id,
        employee_code=emp.employee_code if emp else "UNKNOWN",
        employee_name=f"{emp.first_name} {emp.last_name}" if emp else "Unknown",
        department_name=departments.get(emp.department_id) if emp and emp.department_id else None,
        shift_name=shifts.get(s.shift_id) if s.shift_id else None,
        location_name=locations.get(s.location_id) if s.location_id else None,
        work_date=s.work_date,
        check_in_at=s.check_in_at,
        check_out_at=s.check_out_at,
        status=s.status,
        is_open=s.is_open,
        is_late=s.is_late,
        late_minutes=s.late_minutes,
        is_early_departure=s.is_early_departure,
        early_departure_minutes=s.early_departure_minutes,
        gross_minutes=s.gross_minutes,
        break_minutes=s.break_minutes,
        net_minutes=s.net_minutes,
        overtime_minutes=s.overtime_minutes,
        overtime_approved=s.overtime_approved,
    )


@router.get("/dashboard", response_model=DashboardMetricsOut)
def get_dashboard_metrics(
    auth: AuthContext = Depends(
        require_permissions("attendance:view_all", "attendance:view_department")
    ),
    db: Session = Depends(get_db),
) -> DashboardMetricsOut:
    org = db.get(Organization, auth.organization_id)
    tz = ZoneInfo(org.timezone if org else "Africa/Addis_Ababa")
    today = datetime.now(timezone.utc).astimezone(tz).date()

    emp_query = select(Employee).where(
        Employee.organization_id == auth.organization_id,
        Employee.employment_status == "active",
    )
    scoped_depts = None
    if (
        "attendance:view_all" not in auth.permissions
        and "attendance:view_department" in auth.permissions
    ):
        scoped_depts = auth.assigned_department_ids
        if not scoped_depts:
            return DashboardMetricsOut(
                total_active_employees=0,
                present_today=0,
                absent_today=0,
                late_today=0,
                currently_working=0,
                currently_on_break=0,
                incomplete_attendance=0,
                approved_leave_today=0,
                daily_trend=[],
                department_comparison=[],
            )
        emp_query = emp_query.where(Employee.department_id.in_(scoped_depts))

    active_employees = db.execute(emp_query).scalars().all()
    emp_ids = {e.id for e in active_employees}
    total_active = len(active_employees)

    sessions_today = (
        db.execute(
            select(AttendanceSession).where(
                AttendanceSession.organization_id == auth.organization_id,
                AttendanceSession.work_date == today,
            )
        )
        .scalars()
        .all()
    )
    if scoped_depts is not None:
        sessions_today = [s for s in sessions_today if s.employee_id in emp_ids]

    present_emp_ids = {s.employee_id for s in sessions_today}
    late_emp_ids = {s.employee_id for s in sessions_today if s.is_late}
    currently_working = len([s for s in sessions_today if s.is_open])
    incomplete_count = len(
        [s for s in sessions_today if s.status == "incomplete"]
    )

    open_breaks = (
        db.execute(
            select(BreakRecord).where(
                BreakRecord.organization_id == auth.organization_id,
                BreakRecord.is_open.is_(True),
            )
        )
        .scalars()
        .all()
    )
    if scoped_depts is not None:
        open_breaks = [b for b in open_breaks if b.employee_id in emp_ids]

    approved_leaves = (
        db.execute(
            select(LeaveRequest).where(
                LeaveRequest.organization_id == auth.organization_id,
                LeaveRequest.status == "approved",
                LeaveRequest.start_date <= today,
                LeaveRequest.end_date >= today,
            )
        )
        .scalars()
        .all()
    )
    leave_emp_ids = {
        lv.employee_id
        for lv in approved_leaves
        if scoped_depts is None or lv.employee_id in emp_ids
    }

    absent_today = max(
        0, total_active - len(present_emp_ids | leave_emp_ids)
    )

    # 7-day trend
    trend_start = today - timedelta(days=6)
    trend_sessions = (
        db.execute(
            select(AttendanceSession).where(
                AttendanceSession.organization_id == auth.organization_id,
                AttendanceSession.work_date >= trend_start,
                AttendanceSession.work_date <= today,
            )
        )
        .scalars()
        .all()
    )
    if scoped_depts is not None:
        trend_sessions = [s for s in trend_sessions if s.employee_id in emp_ids]

    daily_trend = []
    for offset in range(7):
        d = trend_start + timedelta(days=offset)
        day_sessions = [s for s in trend_sessions if s.work_date == d]
        present_cnt = len({s.employee_id for s in day_sessions})
        late_cnt = len({s.employee_id for s in day_sessions if s.is_late})
        daily_trend.append(
            {
                "date": d.isoformat(),
                "present": present_cnt,
                "late": late_cnt,
                "absent": max(0, total_active - present_cnt),
            }
        )

    # Department comparison
    depts = (
        db.execute(
            select(Department).where(Department.organization_id == auth.organization_id)
        )
        .scalars()
        .all()
    )
    department_comparison = []
    for dept in depts:
        if scoped_depts is not None and dept.id not in scoped_depts:
            continue
        dept_emps = {e.id for e in active_employees if e.department_id == dept.id}
        dept_present = len(dept_emps & present_emp_ids)
        dept_late = len(dept_emps & late_emp_ids)
        department_comparison.append(
            {
                "department": dept.name,
                "total": len(dept_emps),
                "present": dept_present,
                "late": dept_late,
            }
        )

    return DashboardMetricsOut(
        total_active_employees=total_active,
        present_today=len(present_emp_ids),
        absent_today=absent_today,
        late_today=len(late_emp_ids),
        currently_working=currently_working,
        currently_on_break=len(open_breaks),
        incomplete_attendance=incomplete_count,
        approved_leave_today=len(leave_emp_ids),
        daily_trend=daily_trend,
        department_comparison=department_comparison,
    )


@router.get("/sessions", response_model=List[AttendanceSessionOut])
def list_attendance_sessions(
    work_date: Optional[date] = Query(default=None),
    department_id: Optional[uuid.UUID] = Query(default=None),
    location_id: Optional[uuid.UUID] = Query(default=None),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    is_open: Optional[bool] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    auth: AuthContext = Depends(
        require_permissions(
            "attendance:view_all", "attendance:view_department", "attendance:view_own"
        )
    ),
    db: Session = Depends(get_db),
) -> List[AttendanceSessionOut]:
    query = select(AttendanceSession).where(
        AttendanceSession.organization_id == auth.organization_id
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
        query = query.where(AttendanceSession.employee_id == emp.id)
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
        query = query.where(AttendanceSession.employee_id.in_(dept_emp_ids))

    if work_date:
        query = query.where(AttendanceSession.work_date == work_date)
    if location_id:
        query = query.where(AttendanceSession.location_id == location_id)
    if status_filter:
        query = query.where(AttendanceSession.status == status_filter)
    if is_open is not None:
        query = query.where(AttendanceSession.is_open == is_open)
    if department_id:
        dept_emp_ids = [
            row[0]
            for row in db.execute(
                select(Employee.id).where(
                    Employee.organization_id == auth.organization_id,
                    Employee.department_id == department_id,
                )
            ).all()
        ]
        if not dept_emp_ids:
            return []
        query = query.where(AttendanceSession.employee_id.in_(dept_emp_ids))

    rows = (
        db.execute(
            query.order_by(AttendanceSession.check_in_at.desc()).limit(limit)
        )
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
    departments = {
        d.id: d.name
        for d in db.execute(
            select(Department).where(Department.organization_id == auth.organization_id)
        )
        .scalars()
        .all()
    }
    shifts = {
        s.id: s.name
        for s in db.execute(
            select(Shift).where(Shift.organization_id == auth.organization_id)
        )
        .scalars()
        .all()
    }
    locations = {
        l.id: l.name
        for l in db.execute(
            select(Location).where(Location.organization_id == auth.organization_id)
        )
        .scalars()
        .all()
    }
    return [
        _serialize_session(s, employees, departments, shifts, locations) for s in rows
    ]


# --- Employee Self-Service Endpoints ---
def _get_self_employee(db: Session, auth: AuthContext) -> Employee:
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
        raise NotFoundError("No employee profile is linked to your user account")
    return emp


@router.get("/my/status")
def get_my_attendance_status(
    auth: AuthContext = Depends(require_org_member),
    db: Session = Depends(get_db),
) -> dict:
    emp = _get_self_employee(db, auth)
    open_session = (
        db.execute(
            select(AttendanceSession).where(
                AttendanceSession.organization_id == auth.organization_id,
                AttendanceSession.employee_id == emp.id,
                AttendanceSession.is_open.is_(True),
            )
        )
        .scalars()
        .first()
    )
    open_break = None
    if open_session:
        open_break = (
            db.execute(
                select(BreakRecord).where(
                    BreakRecord.session_id == open_session.id,
                    BreakRecord.is_open.is_(True),
                )
            )
            .scalars()
            .first()
        )
    state = "checked_out"
    if open_session:
        state = "on_break" if open_break else "working"

    return {
        "state": state,
        "open_session_id": open_session.id if open_session else None,
        "check_in_at": open_session.check_in_at if open_session else None,
        "break_started_at": open_break.break_start_at if open_break else None,
    }


@router.post("/my/check-in", response_model=TerminalPunchResponse)
def my_check_in(
    auth: AuthContext = Depends(require_permissions("attendance:record_own")),
    db: Session = Depends(get_db),
) -> TerminalPunchResponse:
    emp = _get_self_employee(db, auth)
    return perform_check_in(
        db,
        organization_id=auth.organization_id,
        employee_code=emp.employee_code,
        verified_employee=emp,
        source="web_employee",
    )


@router.post("/my/check-out", response_model=TerminalPunchResponse)
def my_check_out(
    auth: AuthContext = Depends(require_permissions("attendance:record_own")),
    db: Session = Depends(get_db),
) -> TerminalPunchResponse:
    emp = _get_self_employee(db, auth)
    return perform_check_out(
        db,
        organization_id=auth.organization_id,
        employee_code=emp.employee_code,
        verified_employee=emp,
        source="web_employee",
    )


@router.post("/my/break/start")
def my_break_start(
    auth: AuthContext = Depends(require_permissions("attendance:record_own")),
    db: Session = Depends(get_db),
) -> dict:
    emp = _get_self_employee(db, auth)
    brk = start_employee_break(
        db, organization_id=auth.organization_id, employee=emp
    )
    return {"id": brk.id, "break_start_at": brk.break_start_at, "is_open": brk.is_open}


@router.post("/my/break/end")
def my_break_end(
    auth: AuthContext = Depends(require_permissions("attendance:record_own")),
    db: Session = Depends(get_db),
) -> dict:
    emp = _get_self_employee(db, auth)
    brk = end_employee_break(
        db, organization_id=auth.organization_id, employee=emp
    )
    return {
        "id": brk.id,
        "break_end_at": brk.break_end_at,
        "duration_minutes": brk.duration_minutes,
    }
