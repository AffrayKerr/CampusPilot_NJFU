import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import create_app


def test_health_endpoint():
    app = create_app()
    client = app.test_client()

    response = client.get("/api/health")
    data = response.get_json()

    assert response.status_code == 200
    assert data["success"] is True
    assert data["message"] == "CampusPilot backend is running"


def test_ping_endpoints():
    app = create_app()
    client = app.test_client()

    paths = [
        "/api/account/ping",
        "/api/campus/ping",
        "/api/auth/ping",
        "/api/schedule/ping",
        "/api/seat/ping",
        "/api/logs/ping",
        "/api/notification/ping",
        "/api/feedback/ping",
        "/api/user/ping",
    ]

    for path in paths:
        response = client.get(path)
        data = response.get_json()

        assert response.status_code == 200
        assert data["success"] is True
