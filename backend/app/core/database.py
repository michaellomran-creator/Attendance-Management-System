import errno
import os
import socket
import ssl
from typing import Any, Dict, Generator, List, Optional

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


def _extract_safe_sqlstate(exc: BaseException) -> Optional[str]:
    raw = getattr(exc, "sqlstate", None)
    if isinstance(raw, str) and len(raw) == 5 and raw.isalnum():
        return raw
    return None


def _extract_safe_errno(exc: BaseException) -> Optional[int]:
    raw = getattr(exc, "errno", None)
    if isinstance(raw, int) and not isinstance(raw, bool):
        return raw
    return None


def classify_db_exception(exc: BaseException) -> Dict[str, str]:
    """
    Classify a database exception using only safe structured metadata.
    Never returns raw exception messages, credentials, hostnames, or URLs.
    """
    chain: List[BaseException] = []
    seen: set[int] = set()
    queue: List[Optional[BaseException]] = [exc]
    while queue and len(chain) < 8:
        cur = queue.pop(0)
        if cur is None or id(cur) in seen:
            continue
        seen.add(id(cur))
        chain.append(cur)
        queue.extend(
            [
                getattr(cur, "orig", None),
                getattr(cur, "__cause__", None),
                getattr(cur, "__context__", None),
            ]
        )

    top_class = f"{type(exc).__module__}.{type(exc).__name__}"
    nested_classes = [
        f"{type(item).__module__}.{type(item).__name__}" for item in chain[1:]
    ]

    sqlstate: Optional[str] = None
    os_errno: Optional[int] = None
    for item in chain:
        if sqlstate is None:
            sqlstate = _extract_safe_sqlstate(item)
        if os_errno is None:
            os_errno = _extract_safe_errno(item)

    category = _determine_category(chain, sqlstate, os_errno)

    return {
        "exception": top_class,
        "nested": ",".join(nested_classes) if nested_classes else "none",
        "category": category,
        "sqlstate": sqlstate or "unavailable",
        "os_errno": str(os_errno) if os_errno is not None else "unavailable",
    }


def _determine_category(
    chain: List[BaseException],
    sqlstate: Optional[str],
    os_errno: Optional[int],
) -> str:
    # 1. Inspect exception classes and OS errno first
    for item in chain:
        cls_name = type(item).__name__
        if cls_name == "ConnectionTimeout" or isinstance(item, TimeoutError):
            return "connection_timeout"
        if isinstance(item, socket.gaierror):
            return "dns_resolution_failed"
        if isinstance(item, ConnectionRefusedError):
            return "connection_refused"
        if isinstance(item, ssl.SSLError):
            return "tls_ssl_failure"

    if os_errno is not None:
        if os_errno == errno.ETIMEDOUT:
            return "connection_timeout"
        if os_errno == errno.ECONNREFUSED:
            return "connection_refused"
        if os_errno in {errno.ENETUNREACH, errno.EHOSTUNREACH}:
            return "network_unreachable"

    if sqlstate:
        if sqlstate in {"28P01", "28000"}:
            return "authentication_failed"
        if sqlstate.startswith(("57", "53", "08")):
            return "server_unavailable"

    # 2. Classify in-memory by known static libpq/psycopg substrings without exposing text
    combined = " ".join(str(item).lower() for item in chain)
    if any(
        k in combined
        for k in (
            "could not translate host name",
            "name or service not known",
            "nodename nor servname",
            "temporary failure in name resolution",
            "getaddrinfo failed",
        )
    ):
        return "dns_resolution_failed"
    if "connection refused" in combined:
        return "connection_refused"
    if "timeout expired" in combined or "timed out" in combined:
        return "connection_timeout"
    if "network is unreachable" in combined or "no route to host" in combined:
        return "network_unreachable"
    if any(k in combined for k in ("ssl", "tls", "certificate")):
        return "tls_ssl_failure"
    if any(
        k in combined
        for k in (
            "password authentication failed",
            "authentication failed",
            "no pg_hba.conf entry",
        )
    ):
        return "authentication_failed"
    if any(
        k in combined
        for k in (
            "endpoint is disabled",
            "database system is starting up",
            "too many connections",
            "server closed the connection",
            "connection closed",
            "the database system is shutting down",
        )
    ):
        return "server_unavailable"

    return "unknown_connection_error"


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
