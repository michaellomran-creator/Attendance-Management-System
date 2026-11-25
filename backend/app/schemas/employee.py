from datetime import date, datetime
from typing import List, Optional
import uuid
from pydantic import BaseModel, EmailStr, Field


class EmployeeCreate(BaseModel):
    employee_code: str = Field(min_length=1, max_length=64)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    phone_number: str = Field(min_length=5, max_length=50)
    department_id: Optional[uuid.UUID] = None
    position_id: Optional[uuid.UUID] = None
    location_id: Optional[uuid.UUID] = None
    supervisor_id: Optional[uuid.UUID] = None
    employment_type: str = Field(
        default="full_time", pattern="^(full_time|part_time|contract|temporary)$"
    )
    employment_start_date: date
    employment_status: str = Field(
        default="active", pattern="^(active|inactive|suspended|on_leave|terminated)$"
    )
    notes: Optional[str] = None
    pin: str = Field(min_length=4, max_length=12, pattern="^[0-9]+$")
    create_user_account: bool = False
    user_password: Optional[str] = Field(default=None, min_length=8, max_length=128)


class EmployeeUpdate(BaseModel):
    first_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    last_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = Field(default=None, min_length=5, max_length=50)
    department_id: Optional[uuid.UUID] = None
    position_id: Optional[uuid.UUID] = None
    location_id: Optional[uuid.UUID] = None
    supervisor_id: Optional[uuid.UUID] = None
    employment_type: Optional[str] = Field(
        default=None, pattern="^(full_time|part_time|contract|temporary)$"
    )
    employment_status: Optional[str] = Field(
        default=None, pattern="^(active|inactive|suspended|on_leave|terminated)$"
    )
    notes: Optional[str] = None
    new_pin: Optional[str] = Field(default=None, min_length=4, max_length=12, pattern="^[0-9]+$")


class EmployeeOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    employee_code: str
    user_id: Optional[uuid.UUID] = None
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone_number: str
    department_id: Optional[uuid.UUID] = None
    department_name: Optional[str] = None
    position_id: Optional[uuid.UUID] = None
    position_title: Optional[str] = None
    location_id: Optional[uuid.UUID] = None
    location_name: Optional[str] = None
    supervisor_id: Optional[uuid.UUID] = None
    employment_type: str
    employment_start_date: date
    employment_status: str
    notes: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class EmployeeListResponse(BaseModel):
    items: List[EmployeeOut]
    total: int
    page: int
    page_size: int


class BulkImportRowError(BaseModel):
    row_number: int
    employee_code: Optional[str] = None
    error: str


class BulkImportPreviewRow(BaseModel):
    row_number: int
    employee_code: str
    first_name: str
    last_name: str
    phone_number: str
    email: Optional[str] = None
    department_name: Optional[str] = None
    employment_type: str
    employment_start_date: date


class BulkImportPreviewResponse(BaseModel):
    valid_count: int
    error_count: int
    valid_rows: List[BulkImportPreviewRow]
    errors: List[BulkImportRowError]
