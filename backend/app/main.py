import logging
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import SessionLocal
from app.core.exceptions import register_exception_handlers

logger = logging.getLogger(__name__)


def _extract_safe_sqlstate(orig: Any) -> str:
    raw = getattr(orig, "sqlstate", None)
    if isinstance(raw, str) and len(raw) == 5 and raw.isalnum():
        return raw
    return "unavailable"


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Multi-Organization Workforce Attendance Management Platform by NORAM DIGITAL SOLUTIONS",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=settings.BACKEND_CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)


@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.get("/health", tags=["Health"])
def health_check() -> dict:
    db_status = "ok"
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception as exc:
        orig = getattr(exc, "orig", None)
        logger.error(
            "Database health check failed (exception=%s, dbapi_exception=%s, sqlstate=%s)",
            type(exc).__name__,
            type(orig).__name__ if orig is not None else "none",
            _extract_safe_sqlstate(orig),
        )
        db_status = "unavailable"
    return {"status": "ok" if db_status == "ok" else "degraded", "database": db_status}


app.include_router(api_router, prefix=settings.API_V1_PREFIX)
