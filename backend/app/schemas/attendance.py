from datetime import date, datetime
from typing import List, Optional
import uuid
from pydantic import BaseModel, Field


class TerminalCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    device_identifier: str = Field(min_length=3, max_length=120)
    location_id: Optional[uuid.UUID] = None


class TerminalOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    device_identifier: str
    location_id: Optional[uuid.UUID] = None
    location_name: Optional[str] = None
    is_active: bool
    last_seen_at: Optional[datetime] = None
    created_at: datetime


class TerminalCreatedResponse(TerminalOut):
    terminal_token: str


class TerminalInfoOut(BaseModel):
    terminal_id: uuid.UUID
    terminal_name: str
    organization_id: uuid.UUID
    organization_name: str
    organization_timezone: str
    location_id: Optional[uuid.UUID] = None
    location_name: Optional[str] = None
    break_tracking_enabled: bool
    reset_delay_seconds: int
    server_time_utc: datetime


class TerminalPunchRequest(BaseModel):
    employee_code: str = Field(min_length=1, max_length=64)
    pin: str = Field(min_length=4, max_length=12, pattern="^[0-9]+$")


class TerminalPunchResponse(BaseModel):
    action: str
    employee_name: str
    employee_code: str
    recorded_at_utc: datetime
    status: str
    message: str
    session_id: uuid.UUID
    gross_minutes: int = 0
    break_minutes: int = 0
    net_minutes: int = 0


class AttendanceSessionOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    employee_id: uuid.UUID
    employee_code: str
    employee_name: str
    department_name: Optional[str] = None
    shift_name: Optional[str] = None
    location_name: Optional[str] = None
    work_date: date
    check_in_at: datetime
    check_out_at: Optional[datetime] = None
    status: str
    is_open: bool
    is_late: bool
    late_minutes: int
    is_early_departure: bool
    early_departure_minutes: int
    gross_minutes: int
    break_minutes: int
    net_minutes: int
    overtime_minutes: int
    overtime_approved: bool


class DashboardMetricsOut(BaseModel):
    total_active_employees: int
    present_today: int
    absent_today: int
    late_today: int
    currently_working: int
    currently_on_break: int
    incomplete_attendance: int
    approved_leave_today: int
    daily_trend: List[dict]
    department_comparison: List[dict]
