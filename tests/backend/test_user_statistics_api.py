import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import create_app
from services.db import execute


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


def test_user_statistics_reads_database(app_with_temp_db):
    client = app_with_temp_db.test_client()
    token = login_user(client)
    headers = {"Authorization": f"Bearer {token}"}

    with app_with_temp_db.app_context():
        execute(
            "INSERT INTO schedules (user_id, course_name) VALUES (?, ?)",
            [1, "操作系统"],
        )
        execute(
            "INSERT INTO exams (user_id, course_name, exam_time) VALUES (?, ?, ?)",
            [1, "数据库", "2026-06-15 09:00"],
        )
        execute(
            "INSERT INTO tasks (user_id, title, deadline, status) VALUES (?, ?, ?, ?)",
            [1, "报告", "2026-06-10 23:59", "pending"],
        )
        execute(
            "INSERT INTO tasks (user_id, title, deadline, status) VALUES (?, ?, ?, ?)",
            [1, "作业", "2026-06-11 23:59", "done"],
        )
        execute(
            "INSERT INTO seat_configs (user_id, seat_no, enabled) VALUES (?, ?, ?)",
            [1, "A203", 1],
        )
        execute(
            "INSERT INTO seat_results (user_id, seat_no, status) VALUES (?, ?, ?)",
            [1, "A203", "success"],
        )
        execute(
            "INSERT INTO reminders (user_id, target_type, target_id, remind_before_minutes) VALUES (?, ?, ?, ?)",
            [1, "task", 1, 120],
        )
        execute(
            "INSERT INTO logs (user_id, module, level, message) VALUES (?, ?, ?, ?)",
            [1, "seat", "ERROR", "抢座失败"],
        )

    response = client.get("/api/user/statistics", headers=headers)
    data = response.get_json()

    assert response.status_code == 200
    assert data["success"] is True
    assert data["data"]["schedule"]["course_count"] == 1
    assert data["data"]["schedule"]["exam_count"] == 1
    assert data["data"]["tasks"]["total"] == 2
    assert data["data"]["tasks"]["pending"] == 1
    assert data["data"]["tasks"]["done"] == 1
    assert data["data"]["tasks"]["completion_rate"] == 0.5
    assert data["data"]["seat"]["config_count"] == 1
    assert data["data"]["seat"]["success_count"] == 1
    assert data["data"]["reminders"]["total"] == 1
    assert data["data"]["logs"]["error_count"] == 1
