import os
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import Base, get_db
from app.core.security import rate_limiter
from app.db.seed import seed_initial_platform
from app.main import app

TEST_DB_URL = os.environ.get("TEST_DATABASE_URL", "sqlite:///./test_attendance.db")

connect_args = {"check_same_thread": False} if TEST_DB_URL.startswith("sqlite") else {}
engine = create_engine(TEST_DB_URL, connect_args=connect_args)
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine, expire_on_commit=False
)


@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    rate_limiter._attempts.clear()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    seed_initial_platform(session)
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
