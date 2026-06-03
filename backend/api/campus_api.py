from flask import Blueprint, g, jsonify, request

from services.auth_service import login_required
from services.crypto_service import decrypt_text, encrypt_text
from services.db import execute, fetch_one, init_database
from services.response_helper import error_response, success_response
from services.shell_runner import run_shell
from utils.validators import require_fields


campus_bp = Blueprint("campus", __name__)


@campus_bp.route("/ping", methods=["GET"])
def ping():
    return success_response("campus api is ready")


@campus_bp.route("/bind", methods=["POST"])
@login_required
def bind_campus_account():
    init_database()
    data = request.get_json(silent=True) or {}

    missing = require_fields(data, ["campus_account", "campus_password"])
    if missing:
        return error_response(f"Missing fields: {', '.join(missing)}")

    user_id = g.current_user["id"]
    encrypted_password = encrypt_text(data["campus_password"])
    existing = fetch_one("SELECT id FROM campus_accounts WHERE user_id = ?", [user_id])

    if existing:
        execute(
            """
            UPDATE campus_accounts
            SET campus_account = ?, campus_password_encrypted = ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            """,
            [data["campus_account"], encrypted_password, user_id],
        )
    else:
        execute(
            """
            INSERT INTO campus_accounts (user_id, campus_account, campus_password_encrypted)
            VALUES (?, ?, ?)
            """,
            [user_id, data["campus_account"], encrypted_password],
        )

    return success_response("Campus account bound successfully")


@campus_bp.route("/status", methods=["GET"])
@login_required
def campus_status():
    user_id = g.current_user["id"]
    account = fetch_one(
        """
        SELECT campus_account, webvpn_cookie_path, last_login_at, session_valid, updated_at
        FROM campus_accounts
        WHERE user_id = ?
        """,
        [user_id],
    )

    if not account:
        return success_response("Campus account is not bound", {"bound": False})

    return success_response(
        "Campus account status",
        {
            "bound": True,
            "campus_account": account["campus_account"],
            "webvpn_cookie_path": account.get("webvpn_cookie_path", ""),
            "last_login_at": account.get("last_login_at", ""),
            "session_valid": bool(account.get("session_valid", 0)),
            "updated_at": account.get("updated_at", ""),
        },
    )


@campus_bp.route("/update", methods=["POST"])
@login_required
def update_campus_account():
    return bind_campus_account()


@campus_bp.route("/unbind", methods=["POST"])
@login_required
def unbind_campus_account():
    user_id = g.current_user["id"]
    execute("DELETE FROM campus_accounts WHERE user_id = ?", [user_id])
    return success_response("Campus account unbound successfully")


@campus_bp.route("/webvpn-login", methods=["POST"])
@login_required
def webvpn_login_with_bound_account():
    user_id = g.current_user["id"]
    account = fetch_one("SELECT * FROM campus_accounts WHERE user_id = ?", [user_id])
    if not account:
        return error_response("Campus account is not bound")

    campus_password = decrypt_text(account["campus_password_encrypted"])
    result = run_shell(
        "shell/auth/login.sh",
        [
            account["campus_account"],
            campus_password,
            g.current_user.get("email", ""),
            user_id,
        ],
        timeout=60,
    )
    return jsonify(result)
