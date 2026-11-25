from datetime import date, time
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hash_secret
from app.models.attendance import AttendanceTerminal
from app.models.employee import Employee, EmployeeCredential
from app.models.organization import Department, Location, Position
from app.models.platform import SubscriptionPlan
from app.models.shift import Shift, ShiftAssignment
from app.models.user import User, UserRole
from app.schemas.platform import OrganizationOnboardRequest
from app.services.platform_service import (
    get_or_create_platform_settings,
    onboard_organization,
)
from app.services.rbac_service import ensure_platform_roles


def seed_initial_platform(db: Session) -> User:
    """Seed platform owner role, default plans, and platform settings."""
    platform_role = ensure_platform_roles(db)
    get_or_create_platform_settings(db)

    admin = (
        db.execute(
            select(User).where(User.email == settings.PLATFORM_ADMIN_EMAIL.lower())
        )
        .scalars()
        .first()
    )
    if not admin:
        admin = User(
            organization_id=None,
            email=settings.PLATFORM_ADMIN_EMAIL.lower(),
            full_name="NORAM Platform Administrator",
            password_hash=hash_secret(settings.PLATFORM_ADMIN_PASSWORD),
            is_platform_admin=True,
            is_active=True,
        )
        db.add(admin)
        db.flush()
        db.add(UserRole(user_id=admin.id, role_id=platform_role.id))

    default_plans = [
        ("starter", "Starter", 25, 1, 2, 1500),
        ("business", "Business", 150, 5, 10, 4500),
        ("enterprise", "Enterprise", 1000, 25, 50, 12000),
    ]
    for code, name, max_emp, max_loc, max_adm, price in default_plans:
        existing_plan = (
            db.execute(select(SubscriptionPlan).where(SubscriptionPlan.code == code))
            .scalars()
            .first()
        )
        if not existing_plan:
            db.add(
                SubscriptionPlan(
                    code=code,
                    name=name,
                    max_employees=max_emp,
                    max_locations=max_loc,
                    max_admins=max_adm,
                    monthly_price=price,
                    currency="ETB",
                )
            )
    db.commit()
    db.refresh(admin)
    return admin


def seed_demonstration_data(db: Session, platform_admin: User) -> None:
    """
    DEVELOPMENT DEMONSTRATION DATA ONLY.
    Populates two sample organizations (Hotel & Hospital) to demonstrate multi-tenancy.
    """
    starter = (
        db.execute(select(SubscriptionPlan).where(SubscriptionPlan.code == "business"))
        .scalars()
        .first()
    )
    if not starter:
        return

    from app.models.organization import Organization

    existing = (
        db.execute(
            select(Organization).where(
                Organization.business_email == "demo-hotel@noramdigital.com"
            )
        )
        .scalars()
        .first()
    )
    if existing:
        return

    hotel = onboard_organization(
        db,
        OrganizationOnboardRequest(
            name="[DEMO] Abyssinia Grand Hotel",
            organization_type="hotel",
            contact_person="Dawit Tadesse",
            business_email="demo-hotel@noramdigital.com",
            phone_number="+251911223344",
            country="Ethiopia",
            timezone="Africa/Addis_Ababa",
            address="Bole Sub-City, Addis Ababa",
            estimated_employees=35,
            plan_id=starter.id,
            billing_cycle="monthly",
            admin_full_name="Dawit Tadesse (Demo Admin)",
            admin_email="hotel-admin@noramdigital.com",
            admin_password="DemoHotelAdmin!2026",
        ),
        actor_user_id=platform_admin.id,
        actor_email=platform_admin.email,
    )

    dept_front = Department(
        organization_id=hotel.id, name="Front Desk", code="FD"
    )
    dept_kitchen = Department(
        organization_id=hotel.id, name="Kitchen & Dining", code="KD"
    )
    loc_main = Location(
        organization_id=hotel.id, name="Main Lobby", code="LOBBY"
    )
    db.add_all([dept_front, dept_kitchen, loc_main])
    db.flush()

    morning_shift = Shift(
        organization_id=hotel.id,
        name="Morning Shift",
        shift_type="morning",
        start_time=time(8, 0),
        end_time=time(16, 0),
        crosses_midnight=False,
        grace_period_minutes=10,
        expected_work_minutes=480,
    )
    night_shift = Shift(
        organization_id=hotel.id,
        name="Night Reception",
        shift_type="night",
        start_time=time(22, 0),
        end_time=time(6, 0),
        crosses_midnight=True,
        grace_period_minutes=10,
        expected_work_minutes=480,
    )
    db.add_all([morning_shift, night_shift])
    db.flush()

    emp1 = Employee(
        organization_id=hotel.id,
        employee_code="HTL-001",
        first_name="Sara",
        last_name="Bekele",
        phone_number="+251911000101",
        department_id=dept_front.id,
        location_id=loc_main.id,
        employment_type="full_time",
        employment_start_date=date(2026, 1, 1),
        employment_status="active",
    )
    db.add(emp1)
    db.flush()
    db.add(
        EmployeeCredential(
            organization_id=hotel.id,
            employee_id=emp1.id,
            pin_hash=hash_secret("1234"),
        )
    )
    db.add(
        ShiftAssignment(
            organization_id=hotel.id,
            shift_id=morning_shift.id,
            employee_id=emp1.id,
            effective_from=date(2026, 1, 1),
        )
    )
    db.commit()


if __name__ == "__main__":
    with SessionLocal() as db:
        admin = seed_initial_platform(db)
        if settings.SEED_DEMO_DATA:
            seed_demonstration_data(db, admin)
        print("Database seed completed.")
