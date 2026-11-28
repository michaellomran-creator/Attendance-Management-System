import logging
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import NullPool, QueuePool

from app.core.config import Settings
from app.core.database import build_engine
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
    def __init__(self, message: str, sqlstate: object = None) -> None:
        super().__init__(message)
        self.sqlstate = sqlstate


def test_health_check_logs_safe_structured_diagnostics_with_valid_sqlstate(
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
    assert (
        "Database health check failed (exception=OperationalError, dbapi_exception=FakeDbapiError, sqlstate=28P01)"
        in full_log
    )
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


def test_health_check_handles_missing_and_invalid_sqlstate_safely(
    monkeypatch, caplog
) -> None:
    import app.main as main_mod

    # 1. Invalid sqlstate value
    orig_invalid = FakeDbapiError("secret_host.neon.tech failure", sqlstate="BAD!@#")
    bad_session_1 = MagicMock()
    bad_session_1.__enter__.return_value.execute.side_effect = OperationalError(
        "SELECT 1", {}, orig_invalid
    )
    monkeypatch.setattr(main_mod, "SessionLocal", lambda: bad_session_1)

    with caplog.at_level(logging.ERROR, logger="app.main"):
        with TestClient(app) as client:
            res1 = client.get("/health")

    assert res1.status_code == 200
    assert res1.json() == {"status": "degraded", "database": "unavailable"}
    log1 = "\n".join(r.getMessage() for r in caplog.records)
    assert "sqlstate=unavailable" in log1
    assert "BAD!@#" not in log1
    assert "secret_host.neon.tech" not in log1

    caplog.clear()

    # 2. Plain exception without orig or sqlstate
    bad_session_2 = MagicMock()
    bad_session_2.__enter__.return_value.execute.side_effect = TimeoutError(
        "secret_pass_999@db.example.com"
    )
    monkeypatch.setattr(main_mod, "SessionLocal", lambda: bad_session_2)

    with caplog.at_level(logging.ERROR, logger="app.main"):
        with TestClient(app) as client:
            res2 = client.get("/health")

    assert res2.status_code == 200
    assert res2.json() == {"status": "degraded", "database": "unavailable"}
    log2 = "\n".join(r.getMessage() for r in caplog.records)
    assert (
        "Database health check failed (exception=TimeoutError, dbapi_exception=none, sqlstate=unavailable)"
        in log2
    )
    assert "secret_pass_999" not in log2
    assert "db.example.com" not in log2
