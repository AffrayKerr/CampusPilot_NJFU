import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import create_app


@pytest.fixture()
def app_with_temp_db(tmp_path):
    app = create_app()
    app.config["DATABASE_PATH"] = tmp_path / "test_campuspilot.db"
    app.config["SECRET_KEY"] = "test-secret-key"
    app.config["ENCRYPTION_KEY"] = "test-encryption-key"
    return app


def login_user(client):
    client.post(
        "/api/account/register",
        json={
            "username": "student01",
            "password": "secret123",
            "email": "student@example.com",
        },
    )
    response = client.post(
        "/api/account/login",
        json={"username": "student01", "password": "secret123"},
    )
    return response.get_json()["data"]["token"]


def test_feedback_submit_requires_fields():
    app = create_app()
    client = app.test_client()

    response = client.post("/api/feedback/submit", json={"type": "seat"})
    data = response.get_json()

    assert response.status_code == 400
    assert data["success"] is False
    assert "Missing fields" in data["message"]


def test_feedback_submit_validates_type():
    app = create_app()
    client = app.test_client()

    response = client.post(
        "/api/feedback/submit",
        json={
            "type": "unknown",
            "title": "测试标题",
            "content": "测试内容",
        },
    )
    data = response.get_json()

    assert response.status_code == 400
    assert data["success"] is False
    assert data["message"] == "Invalid feedback type"


def test_feedback_list_requires_login():
    app = create_app()
    client = app.test_client()

    response = client.get("/api/feedback/list?status=unknown")
    data = response.get_json()

    assert response.status_code == 401
    assert data["success"] is False
    assert data["message"] == "Authentication required"


def test_feedback_list_validates_status_after_login(app_with_temp_db):
    client = app_with_temp_db.test_client()
    token = login_user(client)

    response = client.get(
        "/api/feedback/list?status=unknown",
        headers={"Authorization": f"Bearer {token}"},
    )
    data = response.get_json()

    assert response.status_code == 400
    assert data["success"] is False
    assert data["message"] == "Invalid feedback status"
