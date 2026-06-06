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


def test_school_services_require_campus_binding(app_with_temp_db):
    client = app_with_temp_db.test_client()
    token = login_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    requests = [
        ("POST", "/api/auth/login", {}),
        ("POST", "/api/schedule/sync", {}),
        ("POST", "/api/schedule/exam/sync", {}),
        ("POST", "/api/schedule/changes/detect", {}),
        ("POST", "/api/seat/config", {"seat_no": "A203"}),
        ("GET", "/api/seat/config/list", None),
        ("POST", "/api/seat/config/update", {"id": 1, "seat_no": "A204"}),
        ("POST", "/api/seat/config/delete", {"id": 1}),
        ("POST", "/api/seat/start", {}),
        ("POST", "/api/seat/stop", {}),
        ("GET", "/api/seat/status", None),
        ("GET", "/api/seat/result", None),
    ]

    for method, path, payload in requests:
        if method == "GET":
            response = client.get(path, headers=headers)
        else:
            response = client.post(path, headers=headers, json=payload)

        data = response.get_json()
        assert response.status_code == 400
        assert data["success"] is False
        assert data["message"] == "Campus account is not bound"


def test_school_services_continue_after_campus_binding(app_with_temp_db):
    client = app_with_temp_db.test_client()
    token = login_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    bind_response = client.post(
        "/api/campus/bind",
        headers=headers,
        json={"campus_account": "20230001", "campus_password": "password"},
    )
    bind_data = bind_response.get_json()

    assert bind_response.status_code == 200
    assert bind_data["success"] is True

    response = client.post("/api/schedule/sync", headers=headers, json={})
    data = response.get_json()

    assert response.status_code == 200
    assert data["success"] is False
    assert "Shell script not found" in data["message"]
