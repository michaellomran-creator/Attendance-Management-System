from contextlib import nullcontext
import runpy
from unittest.mock import MagicMock

from alembic import context
from alembic.config import Config
import sqlalchemy

from app.core.config import Settings


def test_process_env_database_url_overrides_dotenv(monkeypatch) -> None:
    sample_url = "postgresql+psycopg://user:p%40ss%25word@neon.example.com:5432/neondb?sslmode=require"
    monkeypatch.setenv("DATABASE_URL", sample_url)
    loaded = Settings()
    assert loaded.DATABASE_URL == sample_url
    assert loaded.DATABASE_URL.startswith("postgresql+psycopg://")


def test_alembic_config_handles_percent_encoded_database_url() -> None:
    sample_url = "postgresql+psycopg://user:p%40ss%25word@localhost:5432/attendance_platform?sslmode=require"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", sample_url.replace("%", "%%"))
    assert cfg.get_main_option("sqlalchemy.url") == sample_url


def test_alembic_env_runs_online_and_offline_with_percent_encoded_url(
    monkeypatch,
) -> None:
    sample_url = "postgresql+psycopg://user:p%40ss%25word@neon.example.com:5432/neondb?sslmode=require"
    monkeypatch.setattr("app.core.config.settings.DATABASE_URL", sample_url)

    # 1. Online mode
    cfg = Config("alembic.ini")
    cfg.config_file_name = None

    captured = {}

    class DummyConn:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    class DummyEngine:
        def connect(self):
            return DummyConn()

    def fake_create_engine(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return DummyEngine()

    monkeypatch.setattr(sqlalchemy, "create_engine", fake_create_engine)
    monkeypatch.setattr(context, "config", cfg, raising=False)
    monkeypatch.setattr(context, "is_offline_mode", lambda: False, raising=False)
    monkeypatch.setattr(context, "configure", MagicMock(), raising=False)
    monkeypatch.setattr(context, "begin_transaction", nullcontext, raising=False)
    monkeypatch.setattr(context, "run_migrations", MagicMock(), raising=False)

    runpy.run_path("alembic/env.py", run_name="__main__")
    assert captured["url"] == sample_url
    assert cfg.get_main_option("sqlalchemy.url") == sample_url

    # 2. Offline mode
    offline_cfg = Config("alembic.ini")
    offline_cfg.config_file_name = None
    configure_mock = MagicMock()
    monkeypatch.setattr(context, "config", offline_cfg, raising=False)
    monkeypatch.setattr(context, "is_offline_mode", lambda: True, raising=False)
    monkeypatch.setattr(context, "configure", configure_mock, raising=False)

    runpy.run_path("alembic/env.py", run_name="__main__")
    assert configure_mock.call_args.kwargs["url"] == sample_url
