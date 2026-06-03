import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import create_app
from scripts.create_admin import create_admin


@pytest.fixture()
def app_with_temp_db(tmp_path):
    app = create_app()
    app.config["DATABASE_PATH"] = tmp_path / "test_campuspilot.db"
    app.config["SECRET_KEY"] = "test-secret-key"
    app.config["ENCRYPTION_KEY"] = "test-encryption-key"
    return app


def register_and_login(client, username="student01"):
    client.post(
        "/api/account/register",
        json={
            "username": username,
            "password": "secret123",
            "email": f"{username}@example.com",
        },
    )
    response = client.post(
        "/api/account/login",
        json={"username": username, "password": "secret123"},
    )
    return response.get_json()["data"]["token"]


def create_admin_and_login(app, client, username="admin01"):
    with app.app_context():
        create_admin(username, "secret123", f"{username}@example.com")

    response = client.post(
        "/api/account/login",
        json={"username": username, "password": "secret123"},
    )
    return response.get_json()["data"]["token"]


def test_admin_routes_require_login(app_with_temp_db):
    client = app_with_temp_db.test_client()

    response = client.get("/api/admin/users")
    data = response.get_json()

    assert response.status_code == 401
    assert data["success"] is False
    assert data["message"] == "Authentication required"


def test_admin_routes_require_admin_role(app_with_temp_db):
    client = app_with_temp_db.test_client()
    token = register_and_login(client, username="student01")

    response = client.get("/api/admin/users", headers={"Authorization": f"Bearer {token}"})
    data = response.get_json()

    assert response.status_code == 403
    assert data["success"] is False
    assert data["message"] == "Admin permission required"


def test_admin_can_update_feedback_email_settings(app_with_temp_db):
    client = app_with_temp_db.test_client()
    token = create_admin_and_login(app_with_temp_db, client)

    response = client.post(
        "/api/admin/settings/feedback-email",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "feedback_email": "admin@example.com",
            "receive_feedback_email": True,
        },
    )
    data = response.get_json()

    assert response.status_code == 200
    assert data["success"] is True

    list_response = client.get(
        "/api/admin/settings/feedback-email",
        headers={"Authorization": f"Bearer {token}"},
    )
    list_data = list_response.get_json()

    assert list_response.status_code == 200
    assert list_data["data"][0]["feedback_email"] == "admin@example.com"


def test_admin_statistics(app_with_temp_db):
    client = app_with_temp_db.test_client()
    token = create_admin_and_login(app_with_temp_db, client)

    response = client.get("/api/admin/statistics", headers={"Authorization": f"Bearer {token}"})
    data = response.get_json()

    assert response.status_code == 200
    assert data["success"] is True
    assert "total_users" in data["data"]
