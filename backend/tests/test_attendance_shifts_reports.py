from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.employee import Employee
from app.models.platform import AuditLog
from app.services.attendance_service import (
    end_employee_break,
    perform_check_in,
    perform_check_out,
    start_employee_break,
)
from tests.test_auth_and_tenancy import _login, _onboard_two_orgs


def test_overnight_shift_and_break_calculations(
    client: TestClient, db: Session
) -> None:
    org_a, _, token_a, _ = _onboard_two_orgs(client, db)

    # Create Night Shift 22:00 - 06:00 (crosses midnight)
    shift_res = client.post(
        "/api/v1/shifts",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "name": "Night Shift",
            "shift_type": "night",
            "start_time": "22:00:00",
            "end_time": "06:00:00",
            "crosses_midnight": True,
            "grace_period_minutes": 10,
            "expected_work_minutes": 480,
            "break_duration_minutes": 30,
        },
    )
    assert shift_res.status_code == 201, shift_res.text
    shift_id = shift_res.json()["id"]

    emp_res = client.post(
        "/api/v1/employees",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "employee_code": "NS-001",
            "first_name": "Meron",
            "last_name": "Alemu",
            "phone_number": "+251911000099",
            "employment_start_date": "2026-01-01",
            "pin": "5678",
        },
    )
    assert emp_res.status_code == 201
    emp_id = emp_res.json()["id"]

    assign_res = client.post(
        "/api/v1/shifts/assignments",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "shift_id": shift_id,
            "employee_id": emp_id,
            "effective_from": "2026-01-01",
        },
    )
    assert assign_res.status_code == 201

    tz = ZoneInfo("Africa/Addis_Ababa")
    # Check in at 22:05 local time (within 10 min grace -> on_time)
    check_in_utc = datetime(2026, 5, 10, 22, 5, tzinfo=tz).astimezone(timezone.utc)
    emp_obj = db.execute(select(Employee).where(Employee.employee_code == "NS-001")).scalar_one()

    ci = perform_check_in(
        db,
        organization_id=emp_obj.organization_id,
        employee_code="NS-001",
        pin="5678",
        now_utc=check_in_utc,
    )
    assert ci.status == "on_time"

    # Break from 01:00 to 01:30 next day (30 mins)
    start_employee_break(
        db,
        organization_id=emp_obj.organization_id,
        employee=emp_obj,
        now_utc=datetime(2026, 5, 11, 1, 0, tzinfo=tz).astimezone(timezone.utc),
    )
    end_employee_break(
        db,
        organization_id=emp_obj.organization_id,
        employee=emp_obj,
        now_utc=datetime(2026, 5, 11, 1, 30, tzinfo=tz).astimezone(timezone.utc),
    )

    # Check out at 06:05 next day -> 480 gross, 30 break, 450 net
    co = perform_check_out(
        db,
        organization_id=emp_obj.organization_id,
        employee_code="NS-001",
        pin="5678",
        now_utc=datetime(2026, 5, 11, 6, 5, tzinfo=tz).astimezone(timezone.utc),
    )
    assert co.gross_minutes == 480
    assert co.break_minutes == 30
    assert co.net_minutes == 450


def test_duplicate_checkin_invalid_checkout_and_correction_audit(
    client: TestClient, db: Session
) -> None:
    _, _, token_a, _ = _onboard_two_orgs(client, db)

    emp_res = client.post(
        "/api/v1/employees",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "employee_code": "EMP-55",
            "first_name": "Kebede",
            "last_name": "Tola",
            "email": "kebede@alpha.example.com",
            "phone_number": "+251911000055",
            "employment_start_date": "2026-01-01",
            "pin": "9999",
            "create_user_account": True,
            "user_password": "EmployeePass!2026",
        },
    )
    assert emp_res.status_code == 201

    term_res = client.post(
        "/api/v1/terminals",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"name": "Gate 1", "device_identifier": "GATE-01"},
    )
    term_token = term_res.json()["terminal_token"]

    # Check-out before check-in fails
    bad_co = client.post(
        "/api/v1/terminals/kiosk/check-out",
        headers={"X-Terminal-Token": term_token},
        json={"employee_code": "EMP-55", "pin": "9999"},
    )
    assert bad_co.status_code == 409

    # Valid check-in
    good_ci = client.post(
        "/api/v1/terminals/kiosk/check-in",
        headers={"X-Terminal-Token": term_token},
        json={"employee_code": "EMP-55", "pin": "9999"},
    )
    assert good_ci.status_code == 200
    session_id = good_ci.json()["session_id"]

    # Duplicate check-in fails
    dup_ci = client.post(
        "/api/v1/terminals/kiosk/check-in",
        headers={"X-Terminal-Token": term_token},
        json={"employee_code": "EMP-55", "pin": "9999"},
    )
    assert dup_ci.status_code == 409

    # Employee submits correction request
    emp_token = _login(client, "kebede@alpha.example.com", "EmployeePass!2026")
    corr_res = client.post(
        "/api/v1/corrections",
        headers={"Authorization": f"Bearer {emp_token}"},
        json={
            "target_date": date.today().isoformat(),
            "session_id": session_id,
            "correction_type": "missed_check_out",
            "requested_check_out_at": datetime.now(timezone.utc).isoformat(),
            "reason": "Forgot to punch out at shift end",
        },
    )
    assert corr_res.status_code == 201, corr_res.text
    corr_id = corr_res.json()["id"]

    # Admin approves correction
    approve_res = client.patch(
        f"/api/v1/corrections/{corr_id}/review",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"status": "approved", "reviewer_comment": "Verified with supervisor"},
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "approved"
    assert "check_in_at" in approve_res.json()["original_snapshot"]

    # Audit log recorded
    audit = db.execute(
        select(AuditLog).where(AuditLog.action == "attendance_correction.approved")
    ).scalar_one_or_none()
    assert audit is not None
