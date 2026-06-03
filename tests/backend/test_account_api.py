import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app import create_app
from services.crypto_service import decrypt_text, encrypt_text


@pytest.fixture()
def app_with_temp_db(tmp_path):
    app = create_app()
    app.config["DATABASE_PATH"] = tmp_path / "test_campuspilot.db"
    app.config["SECRET_KEY"] = "test-secret-key"
    app.config["ENCRYPTION_KEY"] = "test-encryption-key"
    return app


def test_register_and_login(app_with_temp_db):
    client = app_with_temp_db.test_client()

    register_response = client.post(
        "/api/account/register",
        json={
            "username": "student01",
            "password": "secret123",
            "email": "student@example.com",
        },
    )
    register_data = register_response.get_json()

    assert register_response.status_code == 200
    assert register_data["success"] is True
    assert register_data["data"]["role"] == "user"

    login_response = client.post(
        "/api/account/login",
        json={"username": "student01", "password": "secret123"},
    )
    login_data = login_response.get_json()

    assert login_response.status_code == 200
    assert login_data["success"] is True
    assert login_data["data"]["token"]
    assert login_data["data"]["user"]["username"] == "student01"


def test_campus_bind_requires_login(app_with_temp_db):
    client = app_with_temp_db.test_client()

    response = client.post(
        "/api/campus/bind",
        json={"campus_account": "20230001", "campus_password": "password"},
    )
    data = response.get_json()

    assert response.status_code == 401
    assert data["success"] is False
    assert data["message"] == "Authentication required"


def test_encrypt_and_decrypt_text(app_with_temp_db):
    with app_with_temp_db.app_context():
        cipher_text = encrypt_text("campus-password")
        plain_text = decrypt_text(cipher_text)

    assert cipher_text != "campus-password"
    assert plain_text == "campus-password"
