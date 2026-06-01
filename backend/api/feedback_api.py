from flask import Blueprint, jsonify, request

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

    include_context = str(data.get("include_context", False)).lower()

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
def list_feedback():
    status = request.args.get("status", "")

    if status and not validate_feedback_status(status):
        return error_response("Invalid feedback status")

    result = run_shell(
        "shell/feedback/list_feedback.sh",
        [status],
        timeout=20,
    )
    return jsonify(result)


@feedback_bp.route("/<int:feedback_id>", methods=["GET"])
def get_feedback(feedback_id):
    result = run_shell(
        "shell/feedback/get_feedback.sh",
        [feedback_id],
        timeout=20,
    )
    return jsonify(result)


@feedback_bp.route("/update", methods=["POST"])
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
        ],
        timeout=30,
    )
    return jsonify(result)


@feedback_bp.route("/close", methods=["POST"])
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
        ],
        timeout=30,
    )
    return jsonify(result)
