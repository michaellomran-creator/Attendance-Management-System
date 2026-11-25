from datetime import datetime, timezone
from typing import List
import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import (
    AuthContext,
    get_authenticated_terminal,
    require_permissions,
)
from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import generate_terminal_token, hash_token
from app.models.attendance import AttendanceTerminal
from app.models.organization import Location, Organization, OrganizationSettings
from app.schemas.attendance import (
    TerminalCreate,
    TerminalCreatedResponse,
    TerminalInfoOut,
    TerminalOut,
    TerminalPunchRequest,
    TerminalPunchResponse,
)
from app.services.attendance_service import perform_check_in, perform_check_out
from app.services.audit_service import record_audit_log

router = APIRouter(prefix="/terminals", tags=["Attendance Terminals"])


@router.get("", response_model=List[TerminalOut])
def list_terminals(
    auth: AuthContext = Depends(require_permissions("org:manage_terminals")),
    db: Session = Depends(get_db),
) -> List[TerminalOut]:
    rows = (
        db.execute(
            select(AttendanceTerminal)
            .where(AttendanceTerminal.organization_id == auth.organization_id)
            .order_by(AttendanceTerminal.created_at.desc())
        )
        .scalars()
        .all()
    )
    locs = {
        l.id: l.name
        for l in db.execute(
            select(Location).where(Location.organization_id == auth.organization_id)
        )
        .scalars()
        .all()
    }
    return [
        TerminalOut(
            id=t.id,
            organization_id=t.organization_id,
            name=t.name,
            device_identifier=t.device_identifier,
            location_id=t.location_id,
            location_name=locs.get(t.location_id) if t.location_id else None,
            is_active=t.is_active,
            last_seen_at=t.last_seen_at,
            created_at=t.created_at,
        )
        for t in rows
    ]


@router.post(
    "",
    response_model=TerminalCreatedResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_terminal(
    payload: TerminalCreate,
    auth: AuthContext = Depends(require_permissions("org:manage_terminals")),
    db: Session = Depends(get_db),
) -> TerminalCreatedResponse:
    existing = (
        db.execute(
            select(AttendanceTerminal).where(
                AttendanceTerminal.device_identifier == payload.device_identifier.strip()
            )
        )
        .scalars()
        .first()
    )
    if existing:
        raise ConflictError("Device identifier is already registered")

    loc_name = None
    if payload.location_id:
        loc = db.get(Location, payload.location_id)
        if not loc or loc.organization_id != auth.organization_id:
            raise NotFoundError("Location not found")
        loc_name = loc.name

    raw_token = generate_terminal_token()
    terminal = AttendanceTerminal(
        organization_id=auth.organization_id,
        name=payload.name.strip(),
        device_identifier=payload.device_identifier.strip(),
        token_hash=hash_token(raw_token),
        location_id=payload.location_id,
        is_active=True,
    )
    db.add(terminal)
    record_audit_log(
        db,
        action="terminal.registered",
        entity_type="attendance_terminal",
        entity_id=payload.device_identifier.strip(),
        organization_id=auth.organization_id,
        actor_user_id=auth.user.id,
        actor_email=auth.user.email,
    )
    db.commit()
    db.refresh(terminal)

    return TerminalCreatedResponse(
        id=terminal.id,
        organization_id=terminal.organization_id,
        name=terminal.name,
        device_identifier=terminal.device_identifier,
        location_id=terminal.location_id,
        location_name=loc_name,
        is_active=terminal.is_active,
        last_seen_at=terminal.last_seen_at,
        created_at=terminal.created_at,
        terminal_token=raw_token,
    )


@router.patch("/{terminal_id}/toggle", response_model=TerminalOut)
def toggle_terminal_status(
    terminal_id: uuid.UUID,
    auth: AuthContext = Depends(require_permissions("org:manage_terminals")),
    db: Session = Depends(get_db),
) -> TerminalOut:
    terminal = db.get(AttendanceTerminal, terminal_id)
    if not terminal or terminal.organization_id != auth.organization_id:
        raise NotFoundError("Terminal not found")

    terminal.is_active = not terminal.is_active
    record_audit_log(
        db,
        action="terminal.status_toggled",
        entity_type="attendance_terminal",
        entity_id=str(terminal.id),
        organization_id=auth.organization_id,
        actor_user_id=auth.user.id,
        actor_email=auth.user.email,
        metadata={"is_active": terminal.is_active},
    )
    db.commit()
    db.refresh(terminal)
    loc = db.get(Location, terminal.location_id) if terminal.location_id else None
    return TerminalOut(
        id=terminal.id,
        organization_id=terminal.organization_id,
        name=terminal.name,
        device_identifier=terminal.device_identifier,
        location_id=terminal.location_id,
        location_name=loc.name if loc else None,
        is_active=terminal.is_active,
        last_seen_at=terminal.last_seen_at,
        created_at=terminal.created_at,
    )


# --- Kiosk Terminal Endpoints (Authenticated via X-Terminal-Token) ---
@router.get("/kiosk/info", response_model=TerminalInfoOut)
def kiosk_info(
    terminal: AttendanceTerminal = Depends(get_authenticated_terminal),
    db: Session = Depends(get_db),
) -> TerminalInfoOut:
    org = db.get(Organization, terminal.organization_id)
    org_settings = (
        db.execute(
            select(OrganizationSettings).where(
                OrganizationSettings.organization_id == terminal.organization_id
            )
        )
        .scalars()
        .first()
    )
    loc = db.get(Location, terminal.location_id) if terminal.location_id else None
    return TerminalInfoOut(
        terminal_id=terminal.id,
        terminal_name=terminal.name,
        organization_id=terminal.organization_id,
        organization_name=org.name if org else "Organization",
        organization_timezone=org.timezone if org else "Africa/Addis_Ababa",
        location_id=terminal.location_id,
        location_name=loc.name if loc else None,
        break_tracking_enabled=org_settings.break_tracking_enabled if org_settings else True,
        reset_delay_seconds=org_settings.terminal_reset_delay_seconds if org_settings else 4,
        server_time_utc=datetime.now(timezone.utc),
    )


@router.post("/kiosk/check-in", response_model=TerminalPunchResponse)
def kiosk_check_in(
    payload: TerminalPunchRequest,
    terminal: AttendanceTerminal = Depends(get_authenticated_terminal),
    db: Session = Depends(get_db),
) -> TerminalPunchResponse:
    return perform_check_in(
        db,
        organization_id=terminal.organization_id,
        employee_code=payload.employee_code,
        pin=payload.pin,
        terminal=terminal,
        source="terminal_pin",
    )


@router.post("/kiosk/check-out", response_model=TerminalPunchResponse)
def kiosk_check_out(
    payload: TerminalPunchRequest,
    terminal: AttendanceTerminal = Depends(get_authenticated_terminal),
    db: Session = Depends(get_db),
) -> TerminalPunchResponse:
    return perform_check_out(
        db,
        organization_id=terminal.organization_id,
        employee_code=payload.employee_code,
        pin=payload.pin,
        terminal=terminal,
        source="terminal_pin",
    )
