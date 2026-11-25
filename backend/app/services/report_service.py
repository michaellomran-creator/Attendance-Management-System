import csv
from datetime import date
import io
from typing import Any, Dict, List, Optional
import uuid

from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.attendance import AttendanceSession
from app.models.employee import Employee
from app.models.organization import Department, Location
from app.models.requests import LeaveRequest
from app.models.shift import Shift


def generate_daily_report(
    db: Session,
    *,
    organization_id: uuid.UUID,
    report_date: date,
    department_id: Optional[uuid.UUID] = None,
    location_id: Optional[uuid.UUID] = None,
    allowed_department_ids: Optional[set[uuid.UUID]] = None,
) -> List[Dict[str, Any]]:
    query = select(AttendanceSession).where(
        AttendanceSession.organization_id == organization_id,
        AttendanceSession.work_date == report_date,
    )
    sessions = db.execute(query.order_by(AttendanceSession.check_in_at)).scalars().all()

    employees = {
        e.id: e
        for e in db.execute(
            select(Employee).where(Employee.organization_id == organization_id)
        )
        .scalars()
        .all()
    }
    departments = {
        d.id: d.name
        for d in db.execute(
            select(Department).where(Department.organization_id == organization_id)
        )
        .scalars()
        .all()
    }
    shifts = {
        s.id: s.name
        for s in db.execute(
            select(Shift).where(Shift.organization_id == organization_id)
        )
        .scalars()
        .all()
    }
    locations = {
        l.id: l.name
        for l in db.execute(
            select(Location).where(Location.organization_id == organization_id)
        )
        .scalars()
        .all()
    }

    rows: List[Dict[str, Any]] = []
    for s in sessions:
        emp = employees.get(s.employee_id)
        if not emp:
            continue
        if department_id and emp.department_id != department_id:
            continue
        if location_id and s.location_id != location_id and emp.location_id != location_id:
            continue
        if allowed_department_ids is not None and (
            emp.department_id is None or emp.department_id not in allowed_department_ids
        ):
            continue

        rows.append(
            {
                "employee_code": emp.employee_code,
                "employee_name": f"{emp.first_name} {emp.last_name}",
                "department": departments.get(emp.department_id, "Unassigned"),
                "location": locations.get(s.location_id, "Default"),
                "shift": shifts.get(s.shift_id, "Unassigned"),
                "work_date": s.work_date.isoformat(),
                "check_in_at": s.check_in_at.isoformat(),
                "check_out_at": s.check_out_at.isoformat() if s.check_out_at else None,
                "gross_minutes": s.gross_minutes,
                "break_minutes": s.break_minutes,
                "net_minutes": s.net_minutes,
                "overtime_minutes": s.overtime_minutes,
                "late_minutes": s.late_minutes,
                "status": s.status,
            }
        )
    return rows


def generate_monthly_report(
    db: Session,
    *,
    organization_id: uuid.UUID,
    year: int,
    month: int,
    department_id: Optional[uuid.UUID] = None,
    allowed_department_ids: Optional[set[uuid.UUID]] = None,
) -> List[Dict[str, Any]]:
    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1)
    else:
        end_date = date(year, month + 1, 1)

    emp_query = select(Employee).where(
        Employee.organization_id == organization_id,
        Employee.employment_status != "terminated",
    )
    if department_id:
        emp_query = emp_query.where(Employee.department_id == department_id)
    employees = db.execute(emp_query.order_by(Employee.employee_code)).scalars().all()

    departments = {
        d.id: d.name
        for d in db.execute(
            select(Department).where(Department.organization_id == organization_id)
        )
        .scalars()
        .all()
    }

    sessions = (
        db.execute(
            select(AttendanceSession).where(
                AttendanceSession.organization_id == organization_id,
                AttendanceSession.work_date >= start_date,
                AttendanceSession.work_date < end_date,
            )
        )
        .scalars()
        .all()
    )
    approved_leaves = (
        db.execute(
            select(LeaveRequest).where(
                LeaveRequest.organization_id == organization_id,
                LeaveRequest.status == "approved",
                LeaveRequest.start_date < end_date,
                LeaveRequest.end_date >= start_date,
            )
        )
        .scalars()
        .all()
    )

    sessions_by_emp: Dict[uuid.UUID, List[AttendanceSession]] = {}
    for s in sessions:
        sessions_by_emp.setdefault(s.employee_id, []).append(s)

    leave_days_by_emp: Dict[uuid.UUID, int] = {}
    for lv in approved_leaves:
        overlap_start = max(lv.start_date, start_date)
        overlap_end = min(lv.end_date, end_date)
        days = max(0, (overlap_end - overlap_start).days + 1)
        leave_days_by_emp[lv.employee_id] = leave_days_by_emp.get(lv.employee_id, 0) + days

    results: List[Dict[str, Any]] = []
    for emp in employees:
        if allowed_department_ids is not None and (
            emp.department_id is None or emp.department_id not in allowed_department_ids
        ):
            continue
        emp_sessions = sessions_by_emp.get(emp.id, [])
        worked_dates = {s.work_date for s in emp_sessions}
        late_days = len({s.work_date for s in emp_sessions if s.is_late})
        total_net_minutes = sum(s.net_minutes for s in emp_sessions)
        total_overtime_minutes = sum(s.overtime_minutes for s in emp_sessions)
        results.append(
            {
                "employee_code": emp.employee_code,
                "employee_name": f"{emp.first_name} {emp.last_name}",
                "department": departments.get(emp.department_id, "Unassigned"),
                "days_worked": len(worked_dates),
                "days_late": late_days,
                "approved_leave_days": leave_days_by_emp.get(emp.id, 0),
                "total_net_hours": round(total_net_minutes / 60.0, 2),
                "total_overtime_hours": round(total_overtime_minutes / 60.0, 2),
            }
        )
    return results


def export_rows_to_csv(rows: List[Dict[str, Any]]) -> bytes:
    output = io.StringIO()
    if not rows:
        return b""
    writer = csv.DictWriter(output, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")


def export_rows_to_excel(rows: List[Dict[str, Any]], sheet_title: str = "Report") -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title[:31]
    if rows:
        headers = list(rows[0].keys())
        ws.append(headers)
        for row in rows:
            ws.append([row.get(h) for h in headers])
    stream = io.BytesIO()
    wb.save(stream)
    return stream.getvalue()
