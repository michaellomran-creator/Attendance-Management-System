from datetime import date, datetime, time, timedelta, timezone
from typing import Optional
import uuid
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import (
    AppException,
    ConflictError,
    ForbiddenError,
    TooManyRequestsError,
    UnauthorizedError,
)
from app.core.security import rate_limiter, verify_secret
from app.models.attendance import (
    AttendanceEvent,
    AttendanceSession,
    AttendanceSummary,
    AttendanceTerminal,
    BreakRecord,
)
from app.models.employee import Employee, EmployeeCredential
from app.models.organization import Organization, OrganizationSettings
from app.models.shift import Shift, ShiftAssignment, ShiftPolicy
from app.schemas.attendance import TerminalPunchResponse


def _org_zone(tz_name: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz_name)
    except Exception:
        return ZoneInfo("UTC")


def _as_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def resolve_employee_shift(
    db: Session,
    *,
    organization_id: uuid.UUID,
    employee: Employee,
    target_date: date,
) -> Optional[Shift]:
    """Resolve active shift: individual assignment > department assignment."""
    emp_assignment = (
        db.execute(
            select(ShiftAssignment)
            .where(
                ShiftAssignment.organization_id == organization_id,
                ShiftAssignment.employee_id == employee.id,
                ShiftAssignment.effective_from <= target_date,
                or_(
                    ShiftAssignment.effective_to.is_(None),
                    ShiftAssignment.effective_to >= target_date,
                ),
            )
            .order_by(ShiftAssignment.is_temporary.desc(), ShiftAssignment.effective_from.desc())
        )
        .scalars()
        .first()
    )
    if emp_assignment:
        shift = db.get(Shift, emp_assignment.shift_id)
        if shift and shift.is_active:
            return shift

    if employee.department_id:
        dept_assignment = (
            db.execute(
                select(ShiftAssignment)
                .where(
                    ShiftAssignment.organization_id == organization_id,
                    ShiftAssignment.department_id == employee.department_id,
                    ShiftAssignment.effective_from <= target_date,
                    or_(
                        ShiftAssignment.effective_to.is_(None),
                        ShiftAssignment.effective_to >= target_date,
                    ),
                )
                .order_by(ShiftAssignment.effective_from.desc())
            )
            .scalars()
            .first()
        )
        if dept_assignment:
            shift = db.get(Shift, dept_assignment.shift_id)
            if shift and shift.is_active:
                return shift

    return None


def _shift_window_utc(
    shift: Shift, work_date: date, tz: ZoneInfo
) -> tuple[datetime, datetime]:
    start_local = datetime.combine(work_date, shift.start_time, tzinfo=tz)
    end_date = work_date + timedelta(days=1) if shift.crosses_midnight else work_date
    end_local = datetime.combine(end_date, shift.end_time, tzinfo=tz)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def _verify_employee_pin(
    db: Session,
    *,
    organization_id: uuid.UUID,
    employee_code: str,
    pin: str,
) -> Employee:
    rate_key = f"pin:{organization_id}:{employee_code.strip().upper()}"
    if not rate_limiter.check_and_record(
        rate_key, settings.PIN_MAX_FAILED_ATTEMPTS * 2, 60
    ):
        raise TooManyRequestsError(
            "Too many PIN attempts. Please wait before trying again."
        )

    employee = (
        db.execute(
            select(Employee).where(
                Employee.organization_id == organization_id,
                Employee.employee_code == employee_code.strip(),
            )
        )
        .scalars()
        .first()
    )
    # Generic error message so we never reveal whether an employee ID exists
    generic_error = "Invalid employee ID or PIN"

    if not employee:
        raise UnauthorizedError(generic_error)

    cred = (
        db.execute(
            select(EmployeeCredential).where(
                EmployeeCredential.employee_id == employee.id,
                EmployeeCredential.organization_id == organization_id,
            )
        )
        .scalars()
        .first()
    )
    now = datetime.now(timezone.utc)
    if not cred or not cred.is_active:
        raise UnauthorizedError(generic_error)

    if cred.locked_until and cred.locked_until > now:
        raise TooManyRequestsError(
            "PIN temporarily locked due to failed attempts. Contact your administrator."
        )

    if not verify_secret(pin, cred.pin_hash):
        cred.failed_attempts += 1
        if cred.failed_attempts >= settings.PIN_MAX_FAILED_ATTEMPTS:
            cred.locked_until = now + timedelta(minutes=settings.PIN_LOCKOUT_MINUTES)
        db.commit()
        raise UnauthorizedError(generic_error)

    if employee.employment_status != "active":
        raise ForbiddenError(
            f"Employee status is '{employee.employment_status}' and cannot record attendance."
        )

    cred.failed_attempts = 0
    cred.locked_until = None
    rate_limiter.reset(rate_key)
    return employee


def _upsert_daily_summary(
    db: Session,
    *,
    organization_id: uuid.UUID,
    employee_id: uuid.UUID,
    summary_date: date,
) -> None:
    sessions = (
        db.execute(
            select(AttendanceSession).where(
                AttendanceSession.organization_id == organization_id,
                AttendanceSession.employee_id == employee_id,
                AttendanceSession.work_date == summary_date,
            )
        )
        .scalars()
        .all()
    )
    if not sessions:
        return

    total_gross = sum(s.gross_minutes for s in sessions)
    total_break = sum(s.break_minutes for s in sessions)
    total_net = sum(s.net_minutes for s in sessions)
    total_ot = sum(s.overtime_minutes for s in sessions)
    late_mins = sum(s.late_minutes for s in sessions)

    # Determine primary status
    statuses = {s.status for s in sessions}
    if "late" in statuses:
        primary = "late"
    elif "incomplete" in statuses:
        primary = "incomplete"
    elif "overtime" in statuses:
        primary = "overtime"
    elif "early_departure" in statuses:
        primary = "early_departure"
    else:
        primary = sessions[0].status

    summary = (
        db.execute(
            select(AttendanceSummary).where(
                AttendanceSummary.organization_id == organization_id,
                AttendanceSummary.employee_id == employee_id,
                AttendanceSummary.summary_date == summary_date,
            )
        )
        .scalars()
        .first()
    )
    if summary:
        summary.primary_status = primary
        summary.total_gross_minutes = total_gross
        summary.total_break_minutes = total_break
        summary.total_net_minutes = total_net
        summary.total_overtime_minutes = total_ot
        summary.late_minutes = late_mins
    else:
        db.add(
            AttendanceSummary(
                organization_id=organization_id,
                employee_id=employee_id,
                summary_date=summary_date,
                primary_status=primary,
                total_gross_minutes=total_gross,
                total_break_minutes=total_break,
                total_net_minutes=total_net,
                total_overtime_minutes=total_ot,
                late_minutes=late_mins,
            )
        )


def perform_check_in(
    db: Session,
    *,
    organization_id: uuid.UUID,
    employee_code: str,
    pin: Optional[str] = None,
    verified_employee: Optional[Employee] = None,
    terminal: Optional[AttendanceTerminal] = None,
    location_id: Optional[uuid.UUID] = None,
    source: str = "terminal_pin",
    now_utc: Optional[datetime] = None,
) -> TerminalPunchResponse:
    now = now_utc or datetime.now(timezone.utc)
    if verified_employee is not None:
        employee = verified_employee
        if employee.employment_status != "active":
            raise ForbiddenError("Employee is not active")
    else:
        if not pin:
            raise UnauthorizedError("PIN is required")
        employee = _verify_employee_pin(
            db, organization_id=organization_id, employee_code=employee_code, pin=pin
        )

    # Prevent duplicate open sessions
    open_session = (
        db.execute(
            select(AttendanceSession).where(
                AttendanceSession.organization_id == organization_id,
                AttendanceSession.employee_id == employee.id,
                AttendanceSession.is_open.is_(True),
            )
        )
        .scalars()
        .first()
    )
    if open_session:
        raise ConflictError(
            "You already have an active check-in session. Please check out first."
        )

    org = db.get(Organization, organization_id)
    org_settings = (
        db.execute(
            select(OrganizationSettings).where(
                OrganizationSettings.organization_id == organization_id
            )
        )
        .scalars()
        .first()
    )
    tz = _org_zone(org.timezone if org else "Africa/Addis_Ababa")
    local_now = now.astimezone(tz)
    work_date = local_now.date()

    shift = resolve_employee_shift(
        db, organization_id=organization_id, employee=employee, target_date=work_date
    )

    is_late = False
    late_minutes = 0
    status_label = "on_time"

    if shift:
        # Handle overnight shift: if employee checks in early morning (e.g., 01:00) for a 22:00 shift,
        # check if previous day's shift window is still active.
        start_utc, _ = _shift_window_utc(shift, work_date, tz)
        if shift.crosses_midnight and local_now.time() < shift.end_time:
            prev_date = work_date - timedelta(days=1)
            prev_start_utc, prev_end_utc = _shift_window_utc(shift, prev_date, tz)
            if now <= prev_end_utc:
                work_date = prev_date
                start_utc = prev_start_utc

        grace = shift.grace_period_minutes
        deadline = start_utc + timedelta(minutes=grace)
        if now > deadline:
            is_late = True
            late_minutes = max(1, int((now - start_utc).total_seconds() // 60))
            status_label = "late"
    else:
        status_label = "present"

    effective_location_id = (
        terminal.location_id if terminal and terminal.location_id else location_id or employee.location_id
    )

    session = AttendanceSession(
        organization_id=organization_id,
        employee_id=employee.id,
        shift_id=shift.id if shift else None,
        location_id=effective_location_id,
        terminal_id=terminal.id if terminal else None,
        work_date=work_date,
        check_in_at=now,
        status=status_label,
        is_open=True,
        is_late=is_late,
        late_minutes=late_minutes,
    )
    db.add(session)
    db.flush()

    event = AttendanceEvent(
        organization_id=organization_id,
        session_id=session.id,
        employee_id=employee.id,
        location_id=effective_location_id,
        terminal_id=terminal.id if terminal else None,
        event_type="check_in",
        event_timestamp=now,
        source=source,
        metadata_json={"status": status_label, "late_minutes": late_minutes},
    )
    db.add(event)
    if terminal:
        terminal.last_seen_at = now

    _upsert_daily_summary(
        db, organization_id=organization_id, employee_id=employee.id, summary_date=work_date
    )
    db.commit()

    full_name = f"{employee.first_name} {employee.last_name}"
    return TerminalPunchResponse(
        action="check_in",
        employee_name=full_name,
        employee_code=employee.employee_code,
        recorded_at_utc=now,
        status=status_label,
        message=f"Check-in recorded for {full_name}",
        session_id=session.id,
    )


def perform_check_out(
    db: Session,
    *,
    organization_id: uuid.UUID,
    employee_code: str,
    pin: Optional[str] = None,
    verified_employee: Optional[Employee] = None,
    terminal: Optional[AttendanceTerminal] = None,
    source: str = "terminal_pin",
    now_utc: Optional[datetime] = None,
) -> TerminalPunchResponse:
    now = now_utc or datetime.now(timezone.utc)
    if verified_employee is not None:
        employee = verified_employee
    else:
        if not pin:
            raise UnauthorizedError("PIN is required")
        employee = _verify_employee_pin(
            db, organization_id=organization_id, employee_code=employee_code, pin=pin
        )

    open_session = (
        db.execute(
            select(AttendanceSession)
            .where(
                AttendanceSession.organization_id == organization_id,
                AttendanceSession.employee_id == employee.id,
                AttendanceSession.is_open.is_(True),
            )
            .order_by(AttendanceSession.check_in_at.desc())
        )
        .scalars()
        .first()
    )
    if not open_session:
        raise ConflictError("No active check-in session found. Please check in first.")

    # Auto-close any open break on check-out
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
    if open_break:
        open_break.break_end_at = now
        open_break.duration_minutes = max(
            0, int((now - _as_utc(open_break.break_start_at)).total_seconds() // 60)
        )
        open_break.is_open = False

    breaks = (
        db.execute(
            select(BreakRecord).where(BreakRecord.session_id == open_session.id)
        )
        .scalars()
        .all()
    )
    total_break_minutes = sum(b.duration_minutes for b in breaks)
    gross_minutes = max(0, int((now - _as_utc(open_session.check_in_at)).total_seconds() // 60))

    org = db.get(Organization, organization_id)
    org_settings = (
        db.execute(
            select(OrganizationSettings).where(
                OrganizationSettings.organization_id == organization_id
            )
        )
        .scalars()
        .first()
    )
    tz = _org_zone(org.timezone if org else "Africa/Addis_Ababa")

    shift = db.get(Shift, open_session.shift_id) if open_session.shift_id else None
    policy = (
        db.execute(select(ShiftPolicy).where(ShiftPolicy.shift_id == shift.id))
        .scalars()
        .first()
        if shift
        else None
    )

    if policy and policy.auto_deduct_break and total_break_minutes == 0 and shift:
        if gross_minutes > shift.break_duration_minutes:
            total_break_minutes = shift.break_duration_minutes

    net_minutes = max(0, gross_minutes - total_break_minutes)

    is_early = False
    early_minutes = 0
    overtime_minutes = 0
    overtime_approved = False

    expected_minutes = (
        shift.expected_work_minutes
        if shift
        else (org_settings.default_expected_work_minutes if org_settings else 480)
    )
    overtime_threshold = shift.overtime_threshold_minutes if shift else 30

    if shift:
        _, shift_end_utc = _shift_window_utc(shift, open_session.work_date, tz)
        early_limit = shift_end_utc - timedelta(
            minutes=shift.early_departure_threshold_minutes
        )
        if now < early_limit:
            is_early = True
            early_minutes = max(1, int((shift_end_utc - now).total_seconds() // 60))

    overtime_eligible = (
        policy.overtime_eligible
        if policy
        else (org_settings.overtime_enabled if org_settings else True)
    )
    if overtime_eligible and net_minutes > expected_minutes + overtime_threshold:
        overtime_minutes = net_minutes - expected_minutes
        requires_approval = (
            policy.overtime_requires_approval
            if policy
            else (org_settings.overtime_requires_approval if org_settings else True)
        )
        overtime_approved = not requires_approval

    final_status = open_session.status
    if is_early and not open_session.is_late:
        final_status = "early_departure"
    elif overtime_minutes > 0 and not open_session.is_late:
        final_status = "overtime"
    elif not open_session.is_late:
        final_status = "present"

    open_session.check_out_at = now
    open_session.is_open = False
    open_session.gross_minutes = gross_minutes
    open_session.break_minutes = total_break_minutes
    open_session.net_minutes = net_minutes
    open_session.is_early_departure = is_early
    open_session.early_departure_minutes = early_minutes
    open_session.overtime_minutes = overtime_minutes
    open_session.overtime_approved = overtime_approved
    open_session.status = final_status

    db.add(
        AttendanceEvent(
            organization_id=organization_id,
            session_id=open_session.id,
            employee_id=employee.id,
            location_id=open_session.location_id,
            terminal_id=terminal.id if terminal else None,
            event_type="check_out",
            event_timestamp=now,
            source=source,
            metadata_json={
                "gross_minutes": gross_minutes,
                "break_minutes": total_break_minutes,
                "net_minutes": net_minutes,
                "overtime_minutes": overtime_minutes,
            },
        )
    )
    if terminal:
        terminal.last_seen_at = now

    _upsert_daily_summary(
        db,
        organization_id=organization_id,
        employee_id=employee.id,
        summary_date=open_session.work_date,
    )
    db.commit()

    full_name = f"{employee.first_name} {employee.last_name}"
    return TerminalPunchResponse(
        action="check_out",
        employee_name=full_name,
        employee_code=employee.employee_code,
        recorded_at_utc=now,
        status=final_status,
        message=f"Check-out recorded for {full_name}",
        session_id=open_session.id,
        gross_minutes=gross_minutes,
        break_minutes=total_break_minutes,
        net_minutes=net_minutes,
    )


def start_employee_break(
    db: Session,
    *,
    organization_id: uuid.UUID,
    employee: Employee,
    now_utc: Optional[datetime] = None,
) -> BreakRecord:
    now = now_utc or datetime.now(timezone.utc)
    org_settings = (
        db.execute(
            select(OrganizationSettings).where(
                OrganizationSettings.organization_id == organization_id
            )
        )
        .scalars()
        .first()
    )
    if org_settings and not org_settings.break_tracking_enabled:
        raise ForbiddenError("Break tracking is disabled for this organization")

    open_session = (
        db.execute(
            select(AttendanceSession).where(
                AttendanceSession.organization_id == organization_id,
                AttendanceSession.employee_id == employee.id,
                AttendanceSession.is_open.is_(True),
            )
        )
        .scalars()
        .first()
    )
    if not open_session:
        raise ConflictError("Cannot start a break without an active check-in session")

    existing_open_break = (
        db.execute(
            select(BreakRecord).where(
                BreakRecord.session_id == open_session.id,
                BreakRecord.is_open.is_(True),
            )
        )
        .scalars()
        .first()
    )
    if existing_open_break:
        raise ConflictError("A break is already in progress")

    brk = BreakRecord(
        organization_id=organization_id,
        session_id=open_session.id,
        employee_id=employee.id,
        break_start_at=now,
        is_open=True,
    )
    db.add(brk)
    db.add(
        AttendanceEvent(
            organization_id=organization_id,
            session_id=open_session.id,
            employee_id=employee.id,
            event_type="break_start",
            event_timestamp=now,
            source="web_employee",
        )
    )
    db.commit()
    db.refresh(brk)
    return brk


def end_employee_break(
    db: Session,
    *,
    organization_id: uuid.UUID,
    employee: Employee,
    now_utc: Optional[datetime] = None,
) -> BreakRecord:
    now = now_utc or datetime.now(timezone.utc)
    open_break = (
        db.execute(
            select(BreakRecord).where(
                BreakRecord.organization_id == organization_id,
                BreakRecord.employee_id == employee.id,
                BreakRecord.is_open.is_(True),
            )
        )
        .scalars()
        .first()
    )
    if not open_break:
        raise ConflictError("No active break found to end")

    open_break.break_end_at = now
    open_break.duration_minutes = max(
        0, int((now - _as_utc(open_break.break_start_at)).total_seconds() // 60)
    )
    open_break.is_open = False

    db.add(
        AttendanceEvent(
            organization_id=organization_id,
            session_id=open_break.session_id,
            employee_id=employee.id,
            event_type="break_end",
            event_timestamp=now,
            source="web_employee",
            metadata_json={"duration_minutes": open_break.duration_minutes},
        )
    )
    db.commit()
    db.refresh(open_break)
    return open_break
