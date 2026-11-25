from fastapi import APIRouter

from app.api.v1 import (
    attendance,
    auth,
    corrections,
    employees,
    leave,
    notifications,
    organizations,
    platform,
    reports,
    shifts,
    terminals,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(platform.router)
api_router.include_router(organizations.router)
api_router.include_router(employees.router)
api_router.include_router(shifts.router)
api_router.include_router(terminals.router)
api_router.include_router(attendance.router)
api_router.include_router(leave.router)
api_router.include_router(corrections.router)
api_router.include_router(reports.router)
api_router.include_router(notifications.router)
