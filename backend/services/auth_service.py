import secrets
from datetime import datetime, timedelta
from functools import wraps

from flask import current_app, g, request
from werkzeug.security import check_password_hash, generate_password_hash

from services.db import execute, fetch_one
from services.response_helper import error_response


def hash_password(password):
    return generate_password_hash(password)


def verify_password(password_hash, password):
    return check_password_hash(password_hash, password)


def create_session(user_id):
    token = secrets.token_urlsafe(32)
    ttl_hours = current_app.config.get("SESSION_TTL_HOURS", 24)
    expires_at = (datetime.utcnow() + timedelta(hours=ttl_hours)).isoformat(timespec="seconds")

    execute(
        """
        INSERT INTO user_sessions (user_id, token, expires_at)
        VALUES (?, ?, ?)
        """,
        [user_id, token, expires_at],
    )
    return token, expires_at


def revoke_session(token):
    execute(
        "UPDATE user_sessions SET revoked = 1, updated_at = CURRENT_TIMESTAMP WHERE token = ?",
        [token],
    )


def get_token_from_request():
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.replace("Bearer ", "", 1).strip()

    cookie_name = current_app.config.get("SESSION_COOKIE_NAME", "campuspilot_session")
    return request.cookies.get(cookie_name, "")


def get_current_user():
    token = get_token_from_request()
    if not token:
        return None

    return fetch_one(
        """
        SELECT users.id, users.username, users.email, users.role, user_sessions.token
        FROM user_sessions
        JOIN users ON users.id = user_sessions.user_id
        WHERE user_sessions.token = ?
          AND user_sessions.revoked = 0
          AND datetime(user_sessions.expires_at) > datetime('now')
        """,
        [token],
    )


def get_bound_campus_account(user_id):
    return fetch_one(
        """
        SELECT id, campus_account, webvpn_cookie_path, last_login_at, session_valid
        FROM campus_accounts
        WHERE user_id = ?
        """,
        [user_id],
    )


def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user:
            return error_response("Authentication required", status_code=401)

        g.current_user = user
        return view_func(*args, **kwargs)

    return wrapper


def campus_account_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user:
            return error_response("Authentication required", status_code=401)

        campus_account = get_bound_campus_account(user["id"])
        if not campus_account:
            return error_response("Campus account is not bound", status_code=400)

        g.current_user = user
        g.campus_account = campus_account
        return view_func(*args, **kwargs)

    return wrapper


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user:
            return error_response("Authentication required", status_code=401)

        if user.get("role") != "admin":
            return error_response("Admin permission required", status_code=403)

        g.current_user = user
        return view_func(*args, **kwargs)

    return wrapper
