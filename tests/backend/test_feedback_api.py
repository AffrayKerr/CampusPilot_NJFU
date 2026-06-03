import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import create_app


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


def test_feedback_list_validates_status():
    app = create_app()
    client = app.test_client()

    response = client.get("/api/feedback/list?status=unknown")
    data = response.get_json()

    assert response.status_code == 400
    assert data["success"] is False
    assert data["message"] == "Invalid feedback status"
