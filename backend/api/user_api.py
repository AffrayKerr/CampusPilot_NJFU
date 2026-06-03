from flask import Blueprint, g, jsonify, request

from services.auth_service import login_required
from services.db import execute, fetch_one, init_database
from services.response_helper import error_response, success_response
from services.shell_runner import run_shell
from utils.validators import normalize_bool, require_fields


user_bp = Blueprint("user", __name__)


@user_bp.route("/ping", methods=["GET"])
def ping():
    return success_response("user api is ready")


@user_bp.route("/profile", methods=["GET"])
@login_required
def get_profile():
    init_database()
    user = fetch_one(
        """
        SELECT id, username, email, role, created_at, updated_at
        FROM users
        WHERE id = ?
        """,
        [g.current_user["id"]],
    )
    return success_response("User profile", user)


@user_bp.route("/profile", methods=["POST"])
@login_required
def update_profile():
    init_database()
    data = request.get_json(silent=True) or {}

    email = data.get("email", "")
    enable_email = 1 if data.get("enable_email", False) else 0
    enable_desktop = 1 if data.get("enable_desktop", True) else 0

    execute(
        "UPDATE users SET email = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        [email, g.current_user["id"]],
    )
    execute(
        """
        UPDATE notification_settings
        SET enable_email = ?, enable_desktop = ?, updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ?
        """,
        [enable_email, enable_desktop, g.current_user["id"]],
    )
    return success_response("User profile updated")


@user_bp.route("/export", methods=["POST"])
@login_required
def export_config():
    data = request.get_json(silent=True) or {}
    export_path = data.get("export_path", "")

    result = run_shell("shell/user/export_config.sh", [g.current_user["id"], export_path], timeout=30)
    return jsonify(result)


@user_bp.route("/import", methods=["POST"])
@login_required
def import_config():
    data = request.get_json(silent=True) or {}

    missing = require_fields(data, ["import_path"])
    if missing:
        return error_response(f"Missing fields: {', '.join(missing)}")

    result = run_shell("shell/user/import_config.sh", [g.current_user["id"], data["import_path"]], timeout=30)
    return jsonify(result)


@user_bp.route("/statistics", methods=["GET"])
@login_required
def get_statistics():
    result = run_shell("shell/user/get_statistics.sh", [g.current_user["id"]], timeout=20)
    return jsonify(result)
