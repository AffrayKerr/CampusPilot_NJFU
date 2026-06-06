from flask import Blueprint, g, request

from services.auth_service import admin_required
from services.db import execute, fetch_all, fetch_one, init_database
from services.response_helper import error_response, success_response
from utils.validators import require_fields, validate_feedback_status, validate_log_level, validate_log_module


admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/ping", methods=["GET"])
def ping():
    return success_response("admin api is ready")


@admin_bp.route("/settings/feedback-email", methods=["GET"])
@admin_required
def get_feedback_email_settings():
    init_database()
    settings = fetch_all(
        """
        SELECT admin_settings.id, admin_settings.admin_user_id, users.username,
               admin_settings.feedback_email, admin_settings.receive_feedback_email
        FROM admin_settings
        LEFT JOIN users ON users.id = admin_settings.admin_user_id
        ORDER BY admin_settings.id DESC
        """
    )
    return success_response("Admin feedback email settings", settings)


@admin_bp.route("/settings/feedback-email", methods=["POST"])
@admin_required
def update_feedback_email_settings():
    init_database()
    data = request.get_json(silent=True) or {}

    missing = require_fields(data, ["feedback_email"])
    if missing:
        return error_response(f"Missing fields: {', '.join(missing)}")

    receive_feedback_email = 1 if data.get("receive_feedback_email", True) else 0
    admin_user_id = g.current_user["id"]
    existing = fetch_one("SELECT id FROM admin_settings WHERE admin_user_id = ?", [admin_user_id])

    if existing:
        execute(
            """
            UPDATE admin_settings
            SET feedback_email = ?, receive_feedback_email = ?, updated_at = CURRENT_TIMESTAMP
            WHERE admin_user_id = ?
            """,
            [data["feedback_email"], receive_feedback_email, admin_user_id],
        )
    else:
        execute(
            """
            INSERT INTO admin_settings (admin_user_id, feedback_email, receive_feedback_email)
            VALUES (?, ?, ?)
            """,
            [admin_user_id, data["feedback_email"], receive_feedback_email],
        )

    return success_response("Feedback email setting updated")


@admin_bp.route("/users", methods=["GET"])
@admin_required
def list_users():
    init_database()
    limit = request.args.get("limit", 100)
    users = fetch_all(
        """
        SELECT users.id, users.username, users.email, users.role, users.created_at,
               CASE WHEN campus_accounts.id IS NULL THEN 0 ELSE 1 END AS campus_bound
        FROM users
        LEFT JOIN campus_accounts ON campus_accounts.user_id = users.id
        ORDER BY users.id DESC
        LIMIT ?
        """,
        [limit],
    )
    return success_response("User list", users)


@admin_bp.route("/statistics", methods=["GET"])
@admin_required
def statistics():
    init_database()
    total_users = fetch_one("SELECT COUNT(*) AS count FROM users")
    total_feedbacks = fetch_one("SELECT COUNT(*) AS count FROM feedbacks")
    pending_feedbacks = fetch_one("SELECT COUNT(*) AS count FROM feedbacks WHERE status = 'pending'")
    error_logs = fetch_one("SELECT COUNT(*) AS count FROM logs WHERE level = 'ERROR'")

    return success_response(
        "Admin statistics",
        {
            "total_users": total_users["count"],
            "total_feedbacks": total_feedbacks["count"],
            "pending_feedbacks": pending_feedbacks["count"],
            "error_logs": error_logs["count"],
        },
    )


@admin_bp.route("/feedback/list", methods=["GET"])
@admin_required
def list_feedbacks():
    init_database()
    status = request.args.get("status", "")
    limit = request.args.get("limit", 100)

    if status and not validate_feedback_status(status):
        return error_response("Invalid feedback status")

    if status:
        feedbacks = fetch_all(
            """
            SELECT feedbacks.*, users.username
            FROM feedbacks
            LEFT JOIN users ON users.id = feedbacks.user_id
            WHERE feedbacks.status = ?
            ORDER BY feedbacks.id DESC
            LIMIT ?
            """,
            [status, limit],
        )
    else:
        feedbacks = fetch_all(
            """
            SELECT feedbacks.*, users.username
            FROM feedbacks
            LEFT JOIN users ON users.id = feedbacks.user_id
            ORDER BY feedbacks.id DESC
            LIMIT ?
            """,
            [limit],
        )

    return success_response("Feedback list", feedbacks)


@admin_bp.route("/feedback/<int:feedback_id>", methods=["GET"])
@admin_required
def get_feedback(feedback_id):
    init_database()
    feedback = fetch_one(
        """
        SELECT feedbacks.*, users.username
        FROM feedbacks
        LEFT JOIN users ON users.id = feedbacks.user_id
        WHERE feedbacks.id = ?
        """,
        [feedback_id],
    )
    if not feedback:
        return error_response("Feedback not found", status_code=404)

    logs = fetch_all(
        """
        SELECT feedback_logs.*, users.username AS admin_username
        FROM feedback_logs
        LEFT JOIN users ON users.id = feedback_logs.admin_user_id
        WHERE feedback_logs.feedback_id = ?
        ORDER BY feedback_logs.id ASC
        """,
        [feedback_id],
    )
    feedback["process_logs"] = logs
    return success_response("Feedback detail", feedback)


@admin_bp.route("/feedback/update", methods=["POST"])
@admin_required
def update_feedback():
    init_database()
    data = request.get_json(silent=True) or {}

    missing = require_fields(data, ["id", "status"])
    if missing:
        return error_response(f"Missing fields: {', '.join(missing)}")

    if not validate_feedback_status(data["status"]):
        return error_response("Invalid feedback status")

    feedback = fetch_one("SELECT id FROM feedbacks WHERE id = ?", [data["id"]])
    if not feedback:
        return error_response("Feedback not found", status_code=404)

    execute(
        "UPDATE feedbacks SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        [data["status"], data["id"]],
    )
    execute(
        """
        INSERT INTO feedback_logs (feedback_id, admin_user_id, action, message)
        VALUES (?, ?, ?, ?)
        """,
        [data["id"], g.current_user["id"], f"status:{data['status']}", data.get("message", "")],
    )

    return success_response("Feedback updated")


@admin_bp.route("/logs/error", methods=["GET"])
@admin_required
def list_error_logs():
    init_database()
    limit = request.args.get("limit", 100)
    logs = fetch_all(
        """
        SELECT logs.*, users.username
        FROM logs
        LEFT JOIN users ON users.id = logs.user_id
        WHERE logs.level = 'ERROR'
        ORDER BY logs.id DESC
        LIMIT ?
        """,
        [limit],
    )
    return success_response("Error logs", logs)


@admin_bp.route("/logs", methods=["GET"])
@admin_required
def list_logs():
    init_database()
    module = request.args.get("module", "")
    level = request.args.get("level", "")
    limit = request.args.get("limit", 100)

    if module and not validate_log_module(module):
        return error_response("Invalid log module")

    if level and not validate_log_level(level):
        return error_response("Invalid log level")

    conditions = []
    params = []
    if module:
        conditions.append("logs.module = ?")
        params.append(module)
    if level:
        conditions.append("logs.level = ?")
        params.append(level)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)
    logs = fetch_all(
        f"""
        SELECT logs.*, users.username
        FROM logs
        LEFT JOIN users ON users.id = logs.user_id
        {where_clause}
        ORDER BY logs.id DESC
        LIMIT ?
        """,
        params,
    )
    return success_response("Logs", logs)
