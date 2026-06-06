from flask import Blueprint, g, jsonify, request

from services.auth_service import login_required
from services.db import execute, fetch_one, init_database
from services.response_helper import error_response, success_response
from services.shell_runner import run_shell
from utils.validators import require_fields


user_bp = Blueprint("user", __name__)


@user_bp.route("/ping", methods=["GET"])
def ping():
    return success_response("user api is ready")


def count_query(query, params):
    row = fetch_one(query, params)
    return row["count"] if row else 0


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
    init_database()
    user_id = g.current_user["id"]
    campus_account = fetch_one("SELECT id, session_valid FROM campus_accounts WHERE user_id = ?", [user_id])

    task_total = count_query("SELECT COUNT(*) AS count FROM tasks WHERE user_id = ?", [user_id])
    task_done = count_query("SELECT COUNT(*) AS count FROM tasks WHERE user_id = ? AND status = 'done'", [user_id])
    task_pending = count_query("SELECT COUNT(*) AS count FROM tasks WHERE user_id = ? AND status = 'pending'", [user_id])
    task_cancelled = count_query("SELECT COUNT(*) AS count FROM tasks WHERE user_id = ? AND status = 'cancelled'", [user_id])

    statistics = {
        "campus_account": {
            "bound": campus_account is not None,
            "session_valid": bool(campus_account.get("session_valid")) if campus_account else False,
        },
        "schedule": {
            "course_count": count_query("SELECT COUNT(*) AS count FROM schedules WHERE user_id = ?", [user_id]),
            "exam_count": count_query("SELECT COUNT(*) AS count FROM exams WHERE user_id = ?", [user_id]),
            "change_count": count_query("SELECT COUNT(*) AS count FROM change_logs WHERE user_id = ?", [user_id]),
        },
        "tasks": {
            "total": task_total,
            "pending": task_pending,
            "done": task_done,
            "cancelled": task_cancelled,
            "completion_rate": round(task_done / task_total, 4) if task_total else 0,
        },
        "seat": {
            "config_count": count_query("SELECT COUNT(*) AS count FROM seat_configs WHERE user_id = ?", [user_id]),
            "enabled_config_count": count_query(
                "SELECT COUNT(*) AS count FROM seat_configs WHERE user_id = ? AND enabled = 1",
                [user_id],
            ),
            "result_count": count_query("SELECT COUNT(*) AS count FROM seat_results WHERE user_id = ?", [user_id]),
            "success_count": count_query(
                "SELECT COUNT(*) AS count FROM seat_results WHERE user_id = ? AND status = 'success'",
                [user_id],
            ),
            "failed_count": count_query(
                "SELECT COUNT(*) AS count FROM seat_results WHERE user_id = ? AND status IN ('failed', 'failure')",
                [user_id],
            ),
            "error_count": count_query(
                "SELECT COUNT(*) AS count FROM seat_results WHERE user_id = ? AND status = 'error'",
                [user_id],
            ),
        },
        "reminders": {
            "total": count_query("SELECT COUNT(*) AS count FROM reminders WHERE user_id = ?", [user_id]),
            "enabled": count_query("SELECT COUNT(*) AS count FROM reminders WHERE user_id = ? AND enabled = 1", [user_id]),
        },
        "logs": {
            "total": count_query("SELECT COUNT(*) AS count FROM logs WHERE user_id = ?", [user_id]),
            "error_count": count_query("SELECT COUNT(*) AS count FROM logs WHERE user_id = ? AND level = 'ERROR'", [user_id]),
        },
    }
    return success_response("User statistics", statistics)
