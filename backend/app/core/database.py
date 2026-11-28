import os
from typing import Any, Dict, Generator, Optional

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings


def is_vercel_serverless() -> bool:
    """Detect whether the backend is running inside Vercel serverless."""
    return (
        os.environ.get("VERCEL") in {"1", "true", "True"}
        or bool(os.environ.get("VERCEL_ENV"))
    )


def build_engine(database_url: Optional[str] = None) -> Engine:
    """Create a SQLAlchemy engine with serverless-safe pooling on Vercel."""
    url = database_url or settings.DATABASE_URL
    kwargs: Dict[str, Any] = {}

    if url.startswith("postgresql"):
        kwargs["connect_args"] = {"connect_timeout": 10}

    if is_vercel_serverless():
        kwargs["poolclass"] = NullPool
    else:
        kwargs["pool_pre_ping"] = True
        kwargs["pool_size"] = 10
        kwargs["max_overflow"] = 20

    return create_engine(url, **kwargs)


engine = build_engine(settings.DATABASE_URL)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
