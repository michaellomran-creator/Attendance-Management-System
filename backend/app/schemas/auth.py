from datetime import datetime
from typing import List, Optional
import uuid
from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(min_length=10)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)


class UserProfileResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    organization_id: Optional[uuid.UUID] = None
    organization_name: Optional[str] = None
    organization_timezone: Optional[str] = None
    is_platform_admin: bool
    roles: List[str]
    permissions: List[str]
    assigned_department_ids: List[uuid.UUID]
    employee_id: Optional[uuid.UUID] = None
    employee_code: Optional[str] = None
    must_change_password: bool
    last_login_at: Optional[datetime] = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserProfileResponse
