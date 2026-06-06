from flask import Blueprint, current_app, jsonify, make_response, request

from services.auth_service import (
    create_session,
    get_current_user,
    get_token_from_request,
    hash_password,
    login_required,
    revoke_session,
    verify_password,
)
from services.db import execute, fetch_one, init_database
from services.response_helper import error_response, success_response
from utils.validators import require_fields, validate_password, validate_username


account_bp = Blueprint("account", __name__)


@account_bp.route("/ping", methods=["GET"])
def ping():
    return success_response("account api is ready")


@account_bp.route("/register", methods=["POST"])
def register():
    init_database()
    data = request.get_json(silent=True) or {}

    missing = require_fields(data, ["username", "password"])
    if missing:
        return error_response(f"Missing fields: {', '.join(missing)}")

    username = data["username"].strip()
    password = data["password"]
    email = data.get("email", "")
    role = "user"

    if not validate_username(username):
        return error_response("Invalid username")

    if not validate_password(password):
        return error_response("Password must be at least 6 characters")

    existing_user = fetch_one("SELECT id FROM users WHERE username = ?", [username])
    if existing_user:
        return error_response("Username already exists", status_code=409)

    user_id = execute(
        """
        INSERT INTO users (username, password_hash, role, email)
        VALUES (?, ?, ?, ?)
        """,
        [username, hash_password(password), role, email],
    )

    execute(
        "INSERT INTO notification_settings (user_id, enable_email, enable_desktop) VALUES (?, ?, ?)",
        [user_id, 1 if email else 0, 1],
    )

    return success_response(
        "Register successfully",
        {
            "user_id": user_id,
            "username": username,
            "role": role,
            "email": email,
        },
    )


@account_bp.route("/login", methods=["POST"])
def login():
    init_database()
    data = request.get_json(silent=True) or {}

    missing = require_fields(data, ["username", "password"])
    if missing:
        return error_response(f"Missing fields: {', '.join(missing)}")

    user = fetch_one("SELECT * FROM users WHERE username = ?", [data["username"].strip()])
    if not user or not verify_password(user["password_hash"], data["password"]):
        return error_response("Invalid username or password", status_code=401)

    token, expires_at = create_session(user["id"])
    cookie_name = current_app.config.get("SESSION_COOKIE_NAME", "campuspilot_session")

    response = make_response(
        jsonify(
            {
                "success": True,
                "message": "Login successfully",
                "data": {
                    "token": token,
                    "expires_at": expires_at,
                    "user": {
                        "id": user["id"],
                        "username": user["username"],
                        "email": user.get("email", ""),
                        "role": user["role"],
                    },
                },
            }
        )
    )
    response.set_cookie(cookie_name, token, httponly=True, samesite="Lax")
    return response


@account_bp.route("/logout", methods=["POST"])
def logout():
    token = get_token_from_request()
    if token:
        revoke_session(token)

    response = make_response(jsonify({"success": True, "message": "Logout successfully", "data": None}))
    response.delete_cookie(current_app.config.get("SESSION_COOKIE_NAME", "campuspilot_session"))
    return response


@account_bp.route("/me", methods=["GET"])
@login_required
def me():
    user = get_current_user()
    return success_response(
        "Current user",
        {
            "id": user["id"],
            "username": user["username"],
            "email": user.get("email", ""),
            "role": user["role"],
        },
    )


@account_bp.route("/change-password", methods=["POST"])
@login_required
def change_password():
    data = request.get_json(silent=True) or {}
    missing = require_fields(data, ["old_password", "new_password"])
    if missing:
        return error_response(f"Missing fields: {', '.join(missing)}")

    if not validate_password(data["new_password"]):
        return error_response("Password must be at least 6 characters")

    current_user = get_current_user()
    user = fetch_one("SELECT * FROM users WHERE id = ?", [current_user["id"]])
    if not verify_password(user["password_hash"], data["old_password"]):
        return error_response("Old password is incorrect", status_code=401)

    execute(
        "UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        [hash_password(data["new_password"]), current_user["id"]],
    )
    return success_response("Password changed successfully")
