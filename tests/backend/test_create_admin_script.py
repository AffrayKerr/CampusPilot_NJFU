import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import create_app
from scripts.create_admin import create_admin
from services.db import fetch_one


@pytest.fixture()
def app_with_temp_db(tmp_path):
    app = create_app()
    app.config["DATABASE_PATH"] = tmp_path / "test_campuspilot.db"
    app.config["SECRET_KEY"] = "test-secret-key"
    app.config["ENCRYPTION_KEY"] = "test-encryption-key"
    return app


def test_create_admin_script_creates_admin_user(app_with_temp_db):
    with app_with_temp_db.app_context():
        user_id = create_admin("admin01", "secret123", "admin@example.com")
        user = fetch_one("SELECT id, username, role, email FROM users WHERE id = ?", [user_id])

    assert user["username"] == "admin01"
    assert user["role"] == "admin"
    assert user["email"] == "admin@example.com"


def test_create_admin_script_rejects_duplicate_username(app_with_temp_db):
    with app_with_temp_db.app_context():
        create_admin("admin01", "secret123", "admin@example.com")
        with pytest.raises(ValueError, match="Username already exists"):
            create_admin("admin01", "another123", "other@example.com")
