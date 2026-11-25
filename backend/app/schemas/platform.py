from datetime import date, datetime
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, EmailStr, Field


class SubscriptionPlanCreate(BaseModel):
    code: str = Field(min_length=2, max_length=50)
    name: str = Field(min_length=2, max_length=100)
    description: Optional[str] = None
    max_employees: int = Field(gt=0)
    max_locations: int = Field(gt=0)
    max_admins: int = Field(gt=0)
    data_retention_days: int = Field(default=1095, gt=0)
    monthly_price: float = Field(ge=0)
    currency: str = Field(default="ETB", max_length=10)
    support_level: str = Field(default="standard", max_length=50)
    features: Dict[str, Any] = Field(default_factory=dict)


class SubscriptionPlanOut(SubscriptionPlanCreate):
    id: uuid.UUID
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


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
    plan_id: uuid.UUID
    billing_cycle: str = Field(default="monthly")
    admin_full_name: str = Field(min_length=2, max_length=180)
    admin_email: EmailStr
    admin_password: str = Field(min_length=8, max_length=128)


class OrganizationStatusUpdate(BaseModel):
    status: str = Field(pattern="^(active|suspended|inactive)$")
    reason: Optional[str] = None


class SubscriptionUpdate(BaseModel):
    plan_id: Optional[uuid.UUID] = None
    status: Optional[str] = Field(
        default=None, pattern="^(trial|active|past_due|suspended|cancelled|expired)$"
    )
    payment_status: Optional[str] = Field(
        default=None, pattern="^(paid|pending|overdue|waived)$"
    )
    expiry_date: Optional[date] = None
    grace_period_days: Optional[int] = Field(default=None, ge=0, le=90)
    notes: Optional[str] = None


class SubscriptionOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    plan_id: uuid.UUID
    plan_name: Optional[str] = None
    status: str
    billing_cycle: str
    payment_status: str
    start_date: date
    expiry_date: date
    grace_period_days: int
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


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
    subscription: Optional[SubscriptionOut] = None

    model_config = {"from_attributes": True}


class PlatformSettingsUpdate(BaseModel):
    platform_name: Optional[str] = None
    support_email: Optional[EmailStr] = None
    default_timezone: Optional[str] = None
    default_grace_period_days: Optional[int] = Field(default=None, ge=0, le=90)
    maintenance_mode: Optional[bool] = None


class PlatformSettingsOut(BaseModel):
    id: uuid.UUID
    platform_name: str
    support_email: Optional[str] = None
    default_timezone: str
    default_grace_period_days: int
    allow_self_registration: bool
    maintenance_mode: bool

    model_config = {"from_attributes": True}


class PlatformAnalyticsOut(BaseModel):
    total_organizations: int
    active_organizations: int
    suspended_organizations: int
    total_active_employees: int
    total_attendance_sessions_today: int
    subscriptions_by_status: Dict[str, int]
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
