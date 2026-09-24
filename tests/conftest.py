import os
os.environ["DATABASE_URL"] = "sqlite:///./carbon_link_test.db"
os.environ["JWT_SECRET"] = "test-secret-that-is-definitely-longer-than-32-characters"
os.environ["BOOTSTRAP_ADMIN_EMAIL"] = "admin@example.com"
os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = "AdminPassword123!"

import pytest
from fastapi.testclient import TestClient
from app.database import Base, engine
from app.main import app

@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as test_client:
        yield test_client

