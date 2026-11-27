from datetime import datetime
from typing import Any, Dict, Optional
import uuid
from pydantic import BaseModel, EmailStr, Field


class OrganizationOnboardRequest(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    organization_type: str = Field(min_length=2, max_length=80)
    contact_person: str = Field(min_length=2, max_length=150)
    business_email: EmailStr
    phone_number: str = Field(min_length=5, max_length=50)
    country: str = Field(default="Ethiopia", max_length=100)
    timezone: str = Field(default="Africa/Addis_Ababa", max_length=64)
    address: Optional[str] = None
    estimated_employees: Optional[int] = Field(default=None, gt=0)
    admin_full_name: str = Field(min_length=2, max_length=180)
    admin_email: EmailStr
    admin_password: str = Field(min_length=8, max_length=128)


class OrganizationStatusUpdate(BaseModel):
    status: str = Field(pattern="^(active|suspended|inactive)$")
    reason: Optional[str] = None


class OrganizationOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    organization_type: str
    contact_person: str
    business_email: str
    phone_number: str
    country: str
    timezone: str
    address: Optional[str] = None
    estimated_employees: Optional[int] = None
    status: str
    created_at: datetime
    active_employees_count: int = 0

    model_config = {"from_attributes": True}


class PlatformSettingsUpdate(BaseModel):
    platform_name: Optional[str] = None
    support_email: Optional[EmailStr] = None
    default_timezone: Optional[str] = None
    maintenance_mode: Optional[bool] = None


class PlatformSettingsOut(BaseModel):
    id: uuid.UUID
    platform_name: str
    support_email: Optional[str] = None
    default_timezone: str
    allow_self_registration: bool
    maintenance_mode: bool

    model_config = {"from_attributes": True}


class PlatformAnalyticsOut(BaseModel):
    total_organizations: int
    active_organizations: int
    suspended_organizations: int
    total_active_employees: int
    total_attendance_sessions_today: int
    organizations_by_type: Dict[str, int]


class AuditLogOut(BaseModel):
    id: uuid.UUID
    organization_id: Optional[uuid.UUID] = None
    actor_user_id: Optional[uuid.UUID] = None
    actor_email: Optional[str] = None
    action: str
    entity_type: str
    entity_id: Optional[str] = None
    reason: Optional[str] = None
    ip_address: Optional[str] = None
    metadata_json: Dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}
