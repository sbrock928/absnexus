"""Shared test fixtures."""
import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

os.environ["ABSNEXUS_TESTING"] = "1"
os.environ["ABSNEXUS_DATABASE_URL"] = "sqlite:///:memory:"

from app.core.database import Base, get_db
from app.models import *  # noqa
from app import create_app


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", echo=False, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db):
    app = create_app()

    def _override_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _override_db

    # Mock os.getlogin to return test user
    with patch("app.dependencies.os.getlogin", return_value="testuser"):
        # Seed a test user
        user = User(username="testuser", display_name="Test User", role="analytics")
        db.add(user)
        db.flush()
        yield TestClient(app)


@pytest.fixture()
def admin_client(db):
    app = create_app()

    def _override_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _override_db

    with patch("app.dependencies.os.getlogin", return_value="admin"):
        user = User(username="admin", display_name="Admin", role="admin")
        db.add(user)
        db.flush()
        yield TestClient(app)


@pytest.fixture()
def test_servicer(db):
    s = Servicer(name="Wells Fargo", short_code="WF")
    db.add(s)
    db.flush()
    return s


@pytest.fixture()
def test_deal(db, test_servicer):
    d = Deal(name="AMORT 2024-1", servicer_id=test_servicer.id, product_type="ABS Auto", created_by="testuser")
    db.add(d)
    db.flush()
    return d


@pytest.fixture()
def system_var(db):
    v = VariableDefinition(name="total_collections", display_name="Total Collections", scope="system", data_type="decimal")
    db.add(v)
    db.flush()
    return v
