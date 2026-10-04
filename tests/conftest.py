import os
test_database_url = os.environ.get("CARBONLINK_TEST_DATABASE_URL", "sqlite:///./carbon_link_test.db")
if not (test_database_url.startswith("sqlite:") or test_database_url.endswith("/carbon_link_test")):
    raise RuntimeError("Tests must use a dedicated carbon_link_test database")
os.environ["DATABASE_URL"] = test_database_url
os.environ["JWT_SECRET"] = "test-secret-that-is-definitely-longer-than-32-characters"
os.environ["BOOTSTRAP_ADMIN_EMAIL"] = "admin@example.com"
os.environ["BOOTSTRAP_ADMIN_PASSWORD"] = "AdminPassword123!"
os.environ["BLOCKCHAIN_ENABLED"] = "false"
os.environ["ENVIRONMENT"] = "test"

import pytest
from fastapi.testclient import TestClient
from app.database import Base, engine
from app.main import app

@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("app.api.UPLOAD_ROOT", tmp_path / "uploads")
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as test_client:
        yield test_client
