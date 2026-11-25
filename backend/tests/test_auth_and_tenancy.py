from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.platform import SubscriptionPlan


def _login(client: TestClient, email: str, password: str) -> str:
    res = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _onboard_two_orgs(client: TestClient, db: Session) -> tuple[dict, dict, str, str]:
    platform_token = _login(
        client, settings.PLATFORM_ADMIN_EMAIL, settings.PLATFORM_ADMIN_PASSWORD
    )
    plan = db.execute(
        select(SubscriptionPlan).where(SubscriptionPlan.code == "starter")
    ).scalar_one()

    org_a_res = client.post(
        "/api/v1/platform/organizations",
        headers={"Authorization": f"Bearer {platform_token}"},
        json={
            "name": "Alpha Hotel",
            "organization_type": "hotel",
            "contact_person": "Alice",
            "business_email": "alpha@hotel.example.com",
            "phone_number": "+251911111111",
            "country": "Ethiopia",
            "timezone": "Africa/Addis_Ababa",
            "plan_id": str(plan.id),
            "admin_full_name": "Alpha Admin",
            "admin_email": "admin@alpha.example.com",
            "admin_password": "AlphaPassword!2026",
        },
    )
    assert org_a_res.status_code == 201, org_a_res.text

    org_b_res = client.post(
        "/api/v1/platform/organizations",
        headers={"Authorization": f"Bearer {platform_token}"},
        json={
            "name": "Beta Hospital",
            "organization_type": "hospital",
            "contact_person": "Bob",
            "business_email": "beta@hospital.example.com",
            "phone_number": "+251922222222",
            "country": "Ethiopia",
            "timezone": "Africa/Addis_Ababa",
            "plan_id": str(plan.id),
            "admin_full_name": "Beta Admin",
            "admin_email": "admin@beta.example.com",
            "admin_password": "BetaPassword!2026",
        },
    )
    assert org_b_res.status_code == 201, org_b_res.text

    token_a = _login(client, "admin@alpha.example.com", "AlphaPassword!2026")
    token_b = _login(client, "admin@beta.example.com", "BetaPassword!2026")
    return org_a_res.json(), org_b_res.json(), token_a, token_b


def test_tenant_isolation_employees_attendance_and_reports(
    client: TestClient, db: Session
) -> None:
    _, _, token_a, token_b = _onboard_two_orgs(client, db)

    # Org A registers an employee
    emp_a_res = client.post(
        "/api/v1/employees",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "employee_code": "A-001",
            "first_name": "Abebe",
            "last_name": "Tesfaye",
            "phone_number": "+251911000011",
            "employment_start_date": "2026-01-01",
            "pin": "1234",
        },
    )
    assert emp_a_res.status_code == 201, emp_a_res.text
    emp_a_id = emp_a_res.json()["id"]

    # Org B cannot list, read, or update Org A's employee
    list_b = client.get(
        "/api/v1/employees", headers={"Authorization": f"Bearer {token_b}"}
    )
    assert list_b.status_code == 200
    assert list_b.json()["total"] == 0

    get_b = client.get(
        f"/api/v1/employees/{emp_a_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert get_b.status_code == 404

    patch_b = client.patch(
        f"/api/v1/employees/{emp_a_id}",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"first_name": "Hacked"},
    )
    assert patch_b.status_code == 404

    # Org A registers a terminal and checks in employee A-001
    term_res = client.post(
        "/api/v1/terminals",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"name": "Lobby Tablet", "device_identifier": "ALPHA-TAB-01"},
    )
    assert term_res.status_code == 201
    term_token = term_res.json()["terminal_token"]

    ci_res = client.post(
        "/api/v1/terminals/kiosk/check-in",
        headers={"X-Terminal-Token": term_token},
        json={"employee_code": "A-001", "pin": "1234"},
    )
    assert ci_res.status_code == 200, ci_res.text

    # Org B cannot see Org A's attendance sessions or export Org A's reports
    sess_b = client.get(
        "/api/v1/attendance/sessions",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert sess_b.status_code == 200
    assert len(sess_b.json()) == 0

    rep_b = client.get(
        "/api/v1/reports/daily",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert rep_b.status_code == 200
    assert len(rep_b.json()) == 0


def test_department_manager_scoping(client: TestClient, db: Session) -> None:
    _, _, token_a, _ = _onboard_two_orgs(client, db)

    d1 = client.post(
        "/api/v1/organizations/departments",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"name": "Housekeeping"},
    ).json()
    d2 = client.post(
        "/api/v1/organizations/departments",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"name": "Engineering"},
    ).json()

    e1 = client.post(
        "/api/v1/employees",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "employee_code": "HK-01",
            "first_name": "Hanna",
            "last_name": "Girma",
            "phone_number": "+251911000021",
            "department_id": d1["id"],
            "employment_start_date": "2026-01-01",
            "pin": "1111",
        },
    ).json()
    e2 = client.post(
        "/api/v1/employees",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "employee_code": "ENG-01",
            "first_name": "Yonas",
            "last_name": "Mulu",
            "phone_number": "+251911000022",
            "department_id": d2["id"],
            "employment_start_date": "2026-01-01",
            "pin": "2222",
        },
    ).json()

    # Create department manager assigned ONLY to Housekeeping (d1)
    mgr_res = client.post(
        "/api/v1/organizations/users",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "full_name": "HK Supervisor",
            "email": "hk-mgr@alpha.example.com",
            "password": "ManagerPassword!2026",
            "role_code": "department_manager",
            "assigned_department_ids": [d1["id"]],
        },
    )
    assert mgr_res.status_code == 201

    mgr_token = _login(client, "hk-mgr@alpha.example.com", "ManagerPassword!2026")
    emp_list = client.get(
        "/api/v1/employees", headers={"Authorization": f"Bearer {mgr_token}"}
    ).json()
    assert emp_list["total"] == 1
    assert emp_list["items"][0]["id"] == e1["id"]

    # Direct read of Engineering employee is forbidden
    forbidden_res = client.get(
        f"/api/v1/employees/{e2['id']}",
        headers={"Authorization": f"Bearer {mgr_token}"},
    )
    assert forbidden_res.status_code == 403


def test_cross_tenant_fk_injection_and_subscription_suspension(
    client: TestClient, db: Session
) -> None:
    org_a, _, token_a, token_b = _onboard_two_orgs(client, db)
    platform_token = _login(
        client, settings.PLATFORM_ADMIN_EMAIL, settings.PLATFORM_ADMIN_PASSWORD
    )

    # Org B creates a department and position
    dept_b = client.post(
        "/api/v1/organizations/departments",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"name": "Radiology"},
    ).json()
    pos_b = client.post(
        "/api/v1/organizations/positions",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"title": "Radiologist"},
    ).json()

    # Org A cannot attach Org B's department or position to an Org A employee
    bad_emp = client.post(
        "/api/v1/employees",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "employee_code": "A-900",
            "first_name": "Test",
            "last_name": "Cross",
            "phone_number": "+251911000900",
            "position_id": pos_b["id"],
            "employment_start_date": "2026-01-01",
            "pin": "1234",
        },
    )
    assert bad_emp.status_code == 404

    # Org A cannot assign Org B's department to an Org A user
    bad_user = client.post(
        "/api/v1/organizations/users",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "full_name": "Cross Manager",
            "email": "cross@alpha.example.com",
            "password": "ManagerPassword!2026",
            "role_code": "department_manager",
            "assigned_department_ids": [dept_b["id"]],
        },
    )
    assert bad_user.status_code == 404

    # Suspending Org A's subscription blocks Org A API access
    sub_res = client.patch(
        f"/api/v1/platform/organizations/{org_a['id']}/subscription",
        headers={"Authorization": f"Bearer {platform_token}"},
        json={"status": "suspended"},
    )
    assert sub_res.status_code == 200

    blocked = client.get(
        "/api/v1/employees",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert blocked.status_code == 403
