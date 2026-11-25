from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import AuthContext, get_client_ip, get_current_auth
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserProfileResponse,
)
from app.services.auth_service import (
    authenticate_user,
    build_user_profile,
    change_user_password,
    refresh_access_token,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    return authenticate_user(
        db,
        email=payload.email,
        password=payload.password,
        ip_address=get_client_ip(request),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    payload: RefreshTokenRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    return refresh_access_token(db, payload.refresh_token)


@router.get("/me", response_model=UserProfileResponse)
def get_me(
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> UserProfileResponse:
    return build_user_profile(db, auth.user)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: ChangePasswordRequest,
    auth: AuthContext = Depends(get_current_auth),
    db: Session = Depends(get_db),
) -> None:
    change_user_password(
        db, auth.user, payload.current_password, payload.new_password
    )
