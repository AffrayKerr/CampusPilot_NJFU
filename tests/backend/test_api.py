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
        "/api/admin/ping",
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


def test_business_endpoints_require_login():
    app = create_app()
    client = app.test_client()

    protected_requests = [
        ("GET", "/api/auth/status", None),
        ("POST", "/api/schedule/sync", {}),
        ("GET", "/api/schedule/today", None),
        ("POST", "/api/seat/config", {"seat_no": "A203"}),
        ("GET", "/api/seat/result", None),
        ("GET", "/api/logs/list", None),
        ("GET", "/api/notification/settings", None),
        ("GET", "/api/user/profile", None),
    ]

    for method, path, payload in protected_requests:
        if method == "GET":
            response = client.get(path)
        else:
            response = client.post(path, json=payload)

        data = response.get_json()
        assert response.status_code == 401
        assert data["success"] is False
        assert data["message"] == "Authentication required"
