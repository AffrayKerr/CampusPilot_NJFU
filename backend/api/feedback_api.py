from flask import Blueprint, g, jsonify, request

from services.auth_service import get_current_user, login_required
from services.db import execute, fetch_all, fetch_one, init_database
from services.notification_service import notify_admin_feedback
from services.response_helper import error_response, success_response
from services.shell_runner import run_shell
from utils.validators import (
    require_fields,
    validate_feedback_status,
    validate_feedback_type,
    validate_priority,
)


feedback_bp = Blueprint("feedback", __name__)


@feedback_bp.route("/ping", methods=["GET"])
def ping():
    return success_response("feedback api is ready")


@feedback_bp.route("/submit", methods=["POST"])
def submit_feedback():
    init_database()
    data = request.get_json(silent=True) or {}

    missing = require_fields(data, ["type", "title", "content"])
    if missing:
        return error_response(f"Missing fields: {', '.join(missing)}")

    feedback_type = data["type"]
    if not validate_feedback_type(feedback_type):
        return error_response("Invalid feedback type")

    priority = data.get("priority", "medium")
    if not validate_priority(priority):
        return error_response("Invalid feedback priority")

    current_user = get_current_user()
    user_id = current_user["id"] if current_user else None
    include_context = str(data.get("include_context", False)).lower()

    if user_id:
        feedback_id = execute(
            """
            INSERT INTO feedbacks (user_id, type, title, content, contact_email, priority, context_info)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                user_id,
                feedback_type,
                data["title"],
                data["content"],
                data.get("contact_email", current_user.get("email", "")),
                priority,
                data.get("context_info", "") if include_context == "true" else "",
            ],
        )
        notify_result = notify_admin_feedback(feedback_id)
        return success_response(
            "Feedback submitted successfully",
            {
                "feedback_id": feedback_id,
                "notify_admin": notify_result,
            },
        )

    result = run_shell(
        "shell/feedback/submit_feedback.sh",
        [
            feedback_type,
            data["title"],
            data["content"],
            data.get("contact_email", ""),
            priority,
            include_context,
        ],
        timeout=30,
    )
    return jsonify(result)


@feedback_bp.route("/list", methods=["GET"])
@login_required
def list_feedback():
    init_database()
    status = request.args.get("status", "")

    if status and not validate_feedback_status(status):
        return error_response("Invalid feedback status")

    if status:
        feedbacks = fetch_all(
            "SELECT * FROM feedbacks WHERE user_id = ? AND status = ? ORDER BY id DESC",
            [g.current_user["id"], status],
        )
    else:
        feedbacks = fetch_all(
            "SELECT * FROM feedbacks WHERE user_id = ? ORDER BY id DESC",
            [g.current_user["id"]],
        )

    return success_response("Feedback list", feedbacks)


@feedback_bp.route("/<int:feedback_id>", methods=["GET"])
@login_required
def get_feedback(feedback_id):
    init_database()
    feedback = fetch_one(
        "SELECT * FROM feedbacks WHERE id = ? AND user_id = ?",
        [feedback_id, g.current_user["id"]],
    )
    if not feedback:
        return error_response("Feedback not found", status_code=404)

    return success_response("Feedback detail", feedback)


@feedback_bp.route("/update", methods=["POST"])
@login_required
def update_feedback():
    data = request.get_json(silent=True) or {}

    missing = require_fields(data, ["id", "status"])
    if missing:
        return error_response(f"Missing fields: {', '.join(missing)}")

    status = data["status"]
    if not validate_feedback_status(status):
        return error_response("Invalid feedback status")

    result = run_shell(
        "shell/feedback/update_feedback.sh",
        [
            data["id"],
            status,
            data.get("message", ""),
            g.current_user["id"],
        ],
        timeout=30,
    )
    return jsonify(result)


@feedback_bp.route("/close", methods=["POST"])
@login_required
def close_feedback():
    data = request.get_json(silent=True) or {}

    missing = require_fields(data, ["id"])
    if missing:
        return error_response(f"Missing fields: {', '.join(missing)}")

    result = run_shell(
        "shell/feedback/close_feedback.sh",
        [
            data["id"],
            data.get("message", ""),
            g.current_user["id"],
        ],
        timeout=30,
    )
    return jsonify(result)
