import errno
import logging
import socket
import ssl
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import NullPool, QueuePool

from app.core.config import Settings
from app.core.database import build_engine, classify_db_exception
from app.main import app


def test_database_url_normalization_preserves_query_params(monkeypatch) -> None:
    urls = [
        (
            "postgres://neon_user:p%40ss%251@ep-example.neon.tech/neondb?sslmode=require&channel_binding=require",
            "postgresql+psycopg://neon_user:p%40ss%251@ep-example.neon.tech/neondb?sslmode=require&channel_binding=require",
        ),
        (
            "postgresql://neon_user:secret@ep-example.neon.tech/neondb?sslmode=require",
            "postgresql+psycopg://neon_user:secret@ep-example.neon.tech/neondb?sslmode=require",
        ),
        (
            "postgresql+psycopg://neon_user:secret@ep-example.neon.tech/neondb?sslmode=require&channel_binding=require",
            "postgresql+psycopg://neon_user:secret@ep-example.neon.tech/neondb?sslmode=require&channel_binding=require",
        ),
    ]
    for raw, expected in urls:
        monkeypatch.setenv("DATABASE_URL", raw)
        s = Settings()
        assert s.DATABASE_URL == expected


def test_build_engine_uses_nullpool_on_vercel_and_timeout(monkeypatch) -> None:
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("VERCEL_ENV", raising=False)
    eng = build_engine(
        "postgresql+psycopg://user:pass@localhost:5432/attendance_platform?sslmode=require"
    )
    try:
        assert isinstance(eng.pool, NullPool)
        assert eng.dialect.driver == "psycopg"
    finally:
        eng.dispose()


def test_build_engine_uses_queuepool_locally_with_connect_timeout(monkeypatch) -> None:
    monkeypatch.delenv("VERCEL", raising=False)
    monkeypatch.delenv("VERCEL_ENV", raising=False)

    captured = {}
    import app.core.database as db_mod

    real_create_engine = db_mod.create_engine

    def spy_create_engine(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return real_create_engine(url, **kwargs)

    monkeypatch.setattr(db_mod, "create_engine", spy_create_engine)
    eng = db_mod.build_engine(
        "postgresql+psycopg://user:pass@localhost:5432/attendance_platform"
    )
    try:
        assert isinstance(eng.pool, QueuePool)
        assert captured["kwargs"]["pool_pre_ping"] is True
        assert captured["kwargs"]["pool_size"] == 10
        assert captured["kwargs"]["max_overflow"] == 20
        assert captured["kwargs"]["connect_args"] == {"connect_timeout": 10}
    finally:
        eng.dispose()


class FakeDbapiError(Exception):
    def __init__(self, message: str, sqlstate: object = None, err_no: object = None) -> None:
        super().__init__(message)
        self.sqlstate = sqlstate
        if err_no is not None:
            self.errno = err_no


def test_classify_db_exception_categories() -> None:
    dns_err = OperationalError(
        "SELECT 1",
        {},
        FakeDbapiError('could not translate host name "ep-secret.neon.tech" to address'),
    )
    assert classify_db_exception(dns_err)["category"] == "dns_resolution_failed"

    refused_err = OperationalError(
        "SELECT 1",
        {},
        FakeDbapiError("connection refused", err_no=errno.ECONNREFUSED),
    )
    refused_diag = classify_db_exception(refused_err)
    assert refused_diag["category"] == "connection_refused"
    assert refused_diag["os_errno"] == str(errno.ECONNREFUSED)

    timeout_err = OperationalError("SELECT 1", {}, TimeoutError("timed out"))
    assert classify_db_exception(timeout_err)["category"] == "connection_timeout"

    net_err = OperationalError(
        "SELECT 1",
        {},
        FakeDbapiError("network is unreachable", err_no=errno.ENETUNREACH),
    )
    assert classify_db_exception(net_err)["category"] == "network_unreachable"

    ssl_err = OperationalError(
        "SELECT 1", {}, ssl.SSLError("SSL: CERTIFICATE_VERIFY_FAILED")
    )
    assert classify_db_exception(ssl_err)["category"] == "tls_ssl_failure"

    auth_err = OperationalError(
        "SELECT 1",
        {},
        FakeDbapiError('password authentication failed for user "secret_u"', sqlstate="28P01"),
    )
    auth_diag = classify_db_exception(auth_err)
    assert auth_diag["category"] == "authentication_failed"
    assert auth_diag["sqlstate"] == "28P01"

    unavail_err = OperationalError(
        "SELECT 1", {}, FakeDbapiError("endpoint is disabled")
    )
    assert classify_db_exception(unavail_err)["category"] == "server_unavailable"

    gai_err = OperationalError("SELECT 1", {}, socket.gaierror("getaddrinfo failed"))
    assert classify_db_exception(gai_err)["category"] == "dns_resolution_failed"


def test_health_check_logs_safe_structured_diagnostics_and_hides_secrets(
    monkeypatch, caplog
) -> None:
    import app.main as main_mod

    orig_err = FakeDbapiError(
        'FATAL: password authentication failed for user "secret_user" at '
        "postgresql+psycopg://secret_user:secret_pass_123@ep-test.neon.tech/neondb?sslmode=require&token=abc",
        sqlstate="28P01",
    )
    bad_session = MagicMock()
    bad_session.__enter__.return_value.execute.side_effect = OperationalError(
        "SELECT 1", {}, orig_err
    )
    monkeypatch.setattr(main_mod, "SessionLocal", lambda: bad_session)

    with caplog.at_level(logging.ERROR, logger="app.main"):
        with TestClient(app) as client:
            res = client.get("/health")

    assert res.status_code == 200
    assert res.json() == {"status": "degraded", "database": "unavailable"}

    full_log = "\n".join(r.getMessage() for r in caplog.records)
    assert "exception=sqlalchemy.exc.OperationalError" in full_log
    assert f"nested={FakeDbapiError.__module__}.FakeDbapiError" in full_log
    assert "category=authentication_failed" in full_log
    assert "sqlstate=28P01" in full_log
    assert "os_errno=unavailable" in full_log
    for sensitive in (
        "secret_user",
        "secret_pass_123",
        "ep-test.neon.tech",
        "neondb",
        "sslmode=require",
        "token=abc",
        "postgresql+psycopg://",
    ):
        assert sensitive not in full_log
        assert sensitive not in res.text
