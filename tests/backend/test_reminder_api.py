import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import create_app
from services.db import execute, fetch_all


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


def test_notification_settings_include_default_reminders(app_with_temp_db):
    client = app_with_temp_db.test_client()
    token = login_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/notification/settings", headers=headers)
    data = response.get_json()

    assert response.status_code == 200
    assert data["success"] is True
    assert data["data"]["schedule_default_reminders"] == [15]
    assert data["data"]["exam_default_reminders"] == [1440, 120]
    assert data["data"]["task_default_reminders"] == [1440, 120]


def test_notification_settings_update_default_reminders(app_with_temp_db):
    client = app_with_temp_db.test_client()
    token = login_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.post(
        "/api/notification/settings",
        headers=headers,
        json={
            "schedule_default_reminders": [10, 30],
            "exam_default_reminders": [2880, 1440, 120],
            "task_default_reminders": [720],
        },
    )
    data = response.get_json()

    assert response.status_code == 200
    assert data["success"] is True
    assert data["data"]["schedule_default_reminders"] == [10, 30]
    assert data["data"]["exam_default_reminders"] == [2880, 1440, 120]
    assert data["data"]["task_default_reminders"] == [720]


def test_reminder_crud(app_with_temp_db):
    client = app_with_temp_db.test_client()
    token = login_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    with app_with_temp_db.app_context():
        task_id = execute(
            "INSERT INTO tasks (user_id, title, deadline) VALUES (?, ?, ?)",
            [1, "完成报告", "2026-06-10 23:59"],
        )

    add_response = client.post(
        "/api/reminder/add",
        headers=headers,
        json={
            "target_type": "task",
            "target_id": task_id,
            "remind_before_minutes": 120,
        },
    )
    add_data = add_response.get_json()

    assert add_response.status_code == 200
    assert add_data["success"] is True
    assert add_data["data"]["remind_before_minutes"] == 120

    reminder_id = add_data["data"]["id"]
    update_response = client.post(
        "/api/reminder/update",
        headers=headers,
        json={"id": reminder_id, "remind_before_minutes": 60, "enabled": False},
    )
    update_data = update_response.get_json()

    assert update_response.status_code == 200
    assert update_data["data"]["remind_before_minutes"] == 60
    assert update_data["data"]["enabled"] == 0

    list_response = client.get("/api/reminder/list?target_type=task", headers=headers)
    list_data = list_response.get_json()

    assert list_response.status_code == 200
    assert len(list_data["data"]) == 1

    delete_response = client.post("/api/reminder/delete", headers=headers, json={"id": reminder_id})
    delete_data = delete_response.get_json()

    assert delete_response.status_code == 200
    assert delete_data["success"] is True


def test_apply_default_reminders_for_tasks(app_with_temp_db):
    client = app_with_temp_db.test_client()
    token = login_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    with app_with_temp_db.app_context():
        execute(
            "INSERT INTO tasks (user_id, title, deadline) VALUES (?, ?, ?)",
            [1, "完成报告", "2026-06-10 23:59"],
        )

    response = client.post("/api/reminder/defaults/apply", headers=headers, json={"target_type": "task"})
    data = response.get_json()

    assert response.status_code == 200
    assert data["success"] is True
    assert data["data"]["created_count"] == 2

    with app_with_temp_db.app_context():
        reminders = fetch_all("SELECT * FROM reminders WHERE user_id = ? AND target_type = ?", [1, "task"])

    assert sorted([item["remind_before_minutes"] for item in reminders]) == [120, 1440]
