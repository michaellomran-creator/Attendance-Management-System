from datetime import datetime
from typing import List, Optional
import uuid
from pydantic import BaseModel, EmailStr, Field


class OrganizationProfileUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=200)
    contact_person: Optional[str] = Field(default=None, min_length=2, max_length=150)
    business_email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    country: Optional[str] = None
    timezone: Optional[str] = None
    address: Optional[str] = None


class OrganizationSettingsUpdate(BaseModel):
    default_grace_period_minutes: Optional[int] = Field(default=None, ge=0, le=120)
    default_expected_work_minutes: Optional[int] = Field(default=None, ge=60, le=1440)
    default_minimum_work_minutes: Optional[int] = Field(default=None, ge=30, le=1440)
    default_early_departure_threshold_minutes: Optional[int] = Field(
        default=None, ge=0, le=120
    )
    break_tracking_enabled: Optional[bool] = None
    default_break_minutes: Optional[int] = Field(default=None, ge=0, le=240)
    overtime_enabled: Optional[bool] = None
    overtime_requires_approval: Optional[bool] = None
    terminal_reset_delay_seconds: Optional[int] = Field(default=None, ge=1, le=30)
    workweek_days: Optional[List[int]] = None
    allow_employee_correction_requests: Optional[bool] = None


class OrganizationSettingsOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    default_grace_period_minutes: int
    default_expected_work_minutes: int
    default_minimum_work_minutes: int
    default_early_departure_threshold_minutes: int
    break_tracking_enabled: bool
    default_break_minutes: int
    overtime_enabled: bool
    overtime_requires_approval: bool
    terminal_reset_delay_seconds: int
    workweek_days: List[int]
    allow_employee_correction_requests: bool

    model_config = {"from_attributes": True}


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    code: Optional[str] = Field(default=None, max_length=32)
    description: Optional[str] = None
    manager_user_id: Optional[uuid.UUID] = None


class DepartmentUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    code: Optional[str] = Field(default=None, max_length=32)
    description: Optional[str] = None
    manager_user_id: Optional[uuid.UUID] = None
    is_active: Optional[bool] = None


class DepartmentOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    code: Optional[str] = None
    description: Optional[str] = None
    manager_user_id: Optional[uuid.UUID] = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class LocationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    code: Optional[str] = Field(default=None, max_length=32)
    address: Optional[str] = None
    timezone: Optional[str] = None


class LocationUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    code: Optional[str] = Field(default=None, max_length=32)
    address: Optional[str] = None
    timezone: Optional[str] = None
    is_active: Optional[bool] = None


class LocationOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    code: Optional[str] = None
    address: Optional[str] = None
    timezone: Optional[str] = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PositionCreate(BaseModel):
    title: str = Field(min_length=2, max_length=120)
    department_id: Optional[uuid.UUID] = None
    description: Optional[str] = None


class PositionOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    title: str
    department_id: Optional[uuid.UUID] = None
    description: Optional[str] = None
    is_active: bool

    model_config = {"from_attributes": True}


class OrgUserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=180)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role_code: str = Field(
        pattern="^(org_admin|hr_manager|department_manager|employee)$"
    )
    assigned_department_ids: List[uuid.UUID] = Field(default_factory=list)


class OrgUserUpdate(BaseModel):
    full_name: Optional[str] = None
    role_code: Optional[str] = Field(
        default=None, pattern="^(org_admin|hr_manager|department_manager|employee)$"
    )
    assigned_department_ids: Optional[List[uuid.UUID]] = None
    is_active: Optional[bool] = None


class OrgUserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    roles: List[str]
    assigned_department_ids: List[uuid.UUID]
    last_login_at: Optional[datetime] = None
    created_at: datetime
