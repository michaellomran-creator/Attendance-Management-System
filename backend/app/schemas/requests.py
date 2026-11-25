from datetime import date, datetime
from typing import Optional
import uuid
from pydantic import BaseModel, Field


class LeaveTypeCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    code: str = Field(min_length=1, max_length=32)
    is_paid: bool = True
    max_days_per_year: Optional[int] = Field(default=None, ge=0)


class LeaveTypeOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    code: str
    is_paid: bool
    max_days_per_year: Optional[int] = None
    is_active: bool

    model_config = {"from_attributes": True}


class LeaveRequestCreate(BaseModel):
    leave_type_id: uuid.UUID
    start_date: date
    end_date: date
    reason: str = Field(min_length=3, max_length=1000)


class LeaveRequestReview(BaseModel):
    status: str = Field(pattern="^(approved|rejected)$")
    reviewer_comment: Optional[str] = Field(default=None, max_length=1000)


class LeaveRequestOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str
    employee_code: str
    department_name: Optional[str] = None
    leave_type_id: uuid.UUID
    leave_type_name: str
    start_date: date
    end_date: date
    reason: str
    status: str
    reviewed_at: Optional[datetime] = None
    reviewer_comment: Optional[str] = None
    created_at: datetime


class CorrectionRequestCreate(BaseModel):
    target_date: date
    session_id: Optional[uuid.UUID] = None
    correction_type: str = Field(
        pattern="^(missed_check_in|missed_check_out|time_adjustment)$"
    )
    requested_check_in_at: Optional[datetime] = None
    requested_check_out_at: Optional[datetime] = None
    reason: str = Field(min_length=3, max_length=1000)


class CorrectionRequestReview(BaseModel):
    status: str = Field(pattern="^(approved|rejected)$")
    reviewer_comment: Optional[str] = Field(default=None, max_length=1000)


class CorrectionRequestOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: str
    employee_code: str
    session_id: Optional[uuid.UUID] = None
    target_date: date
    correction_type: str
    requested_check_in_at: Optional[datetime] = None
    requested_check_out_at: Optional[datetime] = None
    original_snapshot: dict
    reason: str
    status: str
    reviewed_at: Optional[datetime] = None
    reviewer_comment: Optional[str] = None
    created_at: datetime


class NotificationOut(BaseModel):
    id: uuid.UUID
    title: str
    message: str
    category: str
    is_read: bool
    created_at: datetime

    model_config = {"from_attributes": True}
