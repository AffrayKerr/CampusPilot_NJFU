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


def login_and_bind(client):
    client.post(
        "/api/account/register",
        json={
            "username": "student01",
            "password": "secret123",
            "email": "student@example.com",
        },
    )
    login_response = client.post(
        "/api/account/login",
        json={"username": "student01", "password": "secret123"},
    )
    token = login_response.get_json()["data"]["token"]
    headers = {"Authorization": f"Bearer {token}"}
    client.post(
        "/api/campus/bind",
        headers=headers,
        json={"campus_account": "20230001", "campus_password": "password"},
    )
    return headers


def test_seat_time_slot_must_be_at_least_two_hours(app_with_temp_db):
    client = app_with_temp_db.test_client()
    headers = login_and_bind(client)

    response = client.post(
        "/api/seat/config",
        headers=headers,
        json={
            "seat_no": "A203",
            "reserve_date": "2026-06-08",
            "reserve_time_slots": [
                {"start_time": "07:30", "end_time": "09:00"},
            ],
        },
    )
    data = response.get_json()

    assert response.status_code == 400
    assert data["success"] is False
    assert data["message"] == "Each reserve time slot must be at least 2 hours"


def test_friday_seat_time_slot_must_end_before_20(app_with_temp_db):
    client = app_with_temp_db.test_client()
    headers = login_and_bind(client)

    response = client.post(
        "/api/seat/config",
        headers=headers,
        json={
            "seat_no": "A203",
            "reserve_date": "2026-06-05",
            "reserve_time_slots": [
                {"start_time": "18:30", "end_time": "20:30"},
            ],
        },
    )
    data = response.get_json()

    assert response.status_code == 400
    assert data["success"] is False
    assert data["message"] == "Reserve time must be between 07:30 and 20:00"


def test_regular_day_allows_multiple_valid_seat_time_slots(app_with_temp_db):
    client = app_with_temp_db.test_client()
    headers = login_and_bind(client)

    response = client.post(
        "/api/seat/config",
        headers=headers,
        json={
            "seat_no": "A203",
            "reserve_date": "2026-06-08",
            "reserve_time_slots": [
                {"start_time": "07:30", "end_time": "09:30"},
                {"start_time": "19:00", "end_time": "22:00"},
            ],
        },
    )
    data = response.get_json()

    assert response.status_code == 200
    assert data["success"] is False
    assert "Shell script not found" in data["message"]
