from unittest.mock import MagicMock
import pytest
from sqlalchemy.exc import OperationalError
from app.database import get_db
from app.main import app


def test_health_endpoint_success(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"


def test_health_endpoint_db_failure(client):
    mock_db = MagicMock()
    mock_db.execute.side_effect = OperationalError("connection failure", params=None, orig=Exception("offline"))

    def override_get_db_fail():
        yield mock_db

    app.dependency_overrides[get_db] = override_get_db_fail
    try:
        with pytest.raises(OperationalError):
            client.get("/health")
    finally:
        app.dependency_overrides.clear()
