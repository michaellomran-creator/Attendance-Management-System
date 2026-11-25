from datetime import date
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import AuthContext, require_permissions
from app.services.report_service import (
    export_rows_to_csv,
    export_rows_to_excel,
    generate_daily_report,
    generate_monthly_report,
)

router = APIRouter(prefix="/reports", tags=["Reports & Exports"])


def _allowed_depts(auth: AuthContext) -> Optional[set[uuid.UUID]]:
    if (
        "attendance:view_all" not in auth.permissions
        and "department_manager" in auth.roles
    ):
        return auth.assigned_department_ids
    return None


@router.get("/daily")
def daily_report(
    report_date: date = Query(default_factory=date.today),
    department_id: Optional[uuid.UUID] = Query(default=None),
    location_id: Optional[uuid.UUID] = Query(default=None),
    auth: AuthContext = Depends(require_permissions("report:view")),
    db: Session = Depends(get_db),
) -> list[dict]:
    return generate_daily_report(
        db,
        organization_id=auth.organization_id,
        report_date=report_date,
        department_id=department_id,
        location_id=location_id,
        allowed_department_ids=_allowed_depts(auth),
    )


@router.get("/monthly")
def monthly_report(
    year: int = Query(default_factory=lambda: date.today().year),
    month: int = Query(default_factory=lambda: date.today().month, ge=1, le=12),
    department_id: Optional[uuid.UUID] = Query(default=None),
    auth: AuthContext = Depends(require_permissions("report:view")),
    db: Session = Depends(get_db),
) -> list[dict]:
    return generate_monthly_report(
        db,
        organization_id=auth.organization_id,
        year=year,
        month=month,
        department_id=department_id,
        allowed_department_ids=_allowed_depts(auth),
    )


@router.get("/daily/export")
def export_daily_report(
    report_date: date = Query(default_factory=date.today),
    format: str = Query(default="csv", pattern="^(csv|xlsx)$"),
    department_id: Optional[uuid.UUID] = Query(default=None),
    auth: AuthContext = Depends(require_permissions("report:export")),
    db: Session = Depends(get_db),
) -> Response:
    rows = generate_daily_report(
        db,
        organization_id=auth.organization_id,
        report_date=report_date,
        department_id=department_id,
        allowed_department_ids=_allowed_depts(auth),
    )
    if format == "xlsx":
        content = export_rows_to_excel(rows, f"Daily {report_date.isoformat()}")
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename=daily_attendance_{report_date.isoformat()}.xlsx"
            },
        )
    content = export_rows_to_csv(rows)
    return Response(
        content=content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=daily_attendance_{report_date.isoformat()}.csv"
        },
    )


@router.get("/monthly/export")
def export_monthly_report(
    year: int = Query(default_factory=lambda: date.today().year),
    month: int = Query(default_factory=lambda: date.today().month, ge=1, le=12),
    format: str = Query(default="csv", pattern="^(csv|xlsx)$"),
    department_id: Optional[uuid.UUID] = Query(default=None),
    auth: AuthContext = Depends(require_permissions("report:export")),
    db: Session = Depends(get_db),
) -> Response:
    rows = generate_monthly_report(
        db,
        organization_id=auth.organization_id,
        year=year,
        month=month,
        department_id=department_id,
        allowed_department_ids=_allowed_depts(auth),
    )
    if format == "xlsx":
        content = export_rows_to_excel(rows, f"Monthly {year}-{month:02d}")
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename=monthly_attendance_{year}_{month:02d}.xlsx"
            },
        )
    content = export_rows_to_csv(rows)
    return Response(
        content=content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=monthly_attendance_{year}_{month:02d}.csv"
        },
    )
