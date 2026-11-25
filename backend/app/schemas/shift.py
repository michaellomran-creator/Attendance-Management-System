from datetime import date, datetime, time
from typing import List, Optional
import uuid
from pydantic import BaseModel, Field


class ShiftPolicyIn(BaseModel):
    overtime_eligible: bool = True
    overtime_requires_approval: bool = True
    auto_deduct_break: bool = False
    mark_absent_after_minutes: int = Field(default=120, ge=15, le=720)


class ShiftCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    shift_type: str = Field(
        default="custom",
        pattern="^(morning|afternoon|night|general|rotating|custom)$",
    )
    start_time: time
    end_time: time
    crosses_midnight: bool = False
    applicable_days: List[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])
    break_duration_minutes: int = Field(default=60, ge=0, le=240)
    grace_period_minutes: int = Field(default=10, ge=0, le=120)
    expected_work_minutes: int = Field(default=480, ge=60, le=1440)
    minimum_work_minutes: int = Field(default=240, ge=30, le=1440)
    early_departure_threshold_minutes: int = Field(default=15, ge=0, le=120)
    overtime_threshold_minutes: int = Field(default=30, ge=0, le=240)
    policy: Optional[ShiftPolicyIn] = None


class ShiftUpdate(BaseModel):
    name: Optional[str] = None
    shift_type: Optional[str] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    crosses_midnight: Optional[bool] = None
    applicable_days: Optional[List[int]] = None
    break_duration_minutes: Optional[int] = Field(default=None, ge=0, le=240)
    grace_period_minutes: Optional[int] = Field(default=None, ge=0, le=120)
    expected_work_minutes: Optional[int] = Field(default=None, ge=60, le=1440)
    minimum_work_minutes: Optional[int] = Field(default=None, ge=30, le=1440)
    early_departure_threshold_minutes: Optional[int] = Field(default=None, ge=0, le=120)
    overtime_threshold_minutes: Optional[int] = Field(default=None, ge=0, le=240)
    is_active: Optional[bool] = None
    policy: Optional[ShiftPolicyIn] = None


class ShiftOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    shift_type: str
    start_time: time
    end_time: time
    crosses_midnight: bool
    applicable_days: List[int]
    break_duration_minutes: int
    grace_period_minutes: int
    expected_work_minutes: int
    minimum_work_minutes: int
    early_departure_threshold_minutes: int
    overtime_threshold_minutes: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ShiftAssignmentCreate(BaseModel):
    shift_id: uuid.UUID
    employee_id: Optional[uuid.UUID] = None
    department_id: Optional[uuid.UUID] = None
    effective_from: date
    effective_to: Optional[date] = None
    is_temporary: bool = False
    rotation_group: Optional[str] = None


class ShiftAssignmentOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    shift_id: uuid.UUID
    shift_name: Optional[str] = None
    employee_id: Optional[uuid.UUID] = None
    employee_name: Optional[str] = None
    department_id: Optional[uuid.UUID] = None
    department_name: Optional[str] = None
    effective_from: date
    effective_to: Optional[date] = None
    is_temporary: bool
    rotation_group: Optional[str] = None
    created_at: datetime


class HolidayCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    holiday_date: date
    is_paid: bool = True


class HolidayOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    holiday_date: date
    is_paid: bool

    model_config = {"from_attributes": True}
