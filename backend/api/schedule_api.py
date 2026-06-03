from flask import Blueprint, g, jsonify, request

from services.auth_service import login_required
from services.response_helper import error_response, success_response
from services.shell_runner import run_shell
from utils.validators import require_fields, validate_priority, validate_task_status


schedule_bp = Blueprint("schedule", __name__)


@schedule_bp.route("/ping", methods=["GET"])
def ping():
    return success_response("schedule api is ready")


@schedule_bp.route("/sync", methods=["POST"])
@login_required
def sync_schedule():
    result = run_shell("shell/schedule/sync_schedule.sh", [g.current_user["id"]], timeout=120)
    return jsonify(result)


@schedule_bp.route("/exam/sync", methods=["POST"])
@login_required
def sync_exam():
    result = run_shell("shell/schedule/sync_exam.sh", [g.current_user["id"]], timeout=120)
    return jsonify(result)


@schedule_bp.route("/today", methods=["GET"])
@login_required
def list_today():
    result = run_shell("shell/schedule/list_today.sh", [g.current_user["id"]], timeout=30)
    return jsonify(result)


@schedule_bp.route("/changes/detect", methods=["POST"])
@login_required
def detect_changes():
    result = run_shell("shell/schedule/detect_changes.sh", [g.current_user["id"]], timeout=120)
    return jsonify(result)


@schedule_bp.route("/task/add", methods=["POST"])
@login_required
def add_task():
    data = request.get_json(silent=True) or {}

    missing = require_fields(data, ["title", "deadline"])
    if missing:
        return error_response(f"Missing fields: {', '.join(missing)}")

    priority = data.get("priority", "medium")
    if not validate_priority(priority):
        return error_response("Invalid task priority")

    result = run_shell(
        "shell/schedule/add_task.sh",
        [
            g.current_user["id"],
            data["title"],
            data["deadline"],
            priority,
            data.get("category", ""),
            data.get("repeat_rule", ""),
            data.get("reminder_time", ""),
            data.get("note", ""),
        ],
        timeout=30,
    )
    return jsonify(result)


@schedule_bp.route("/task/update", methods=["POST"])
@login_required
def update_task():
    data = request.get_json(silent=True) or {}

    missing = require_fields(data, ["id"])
    if missing:
        return error_response(f"Missing fields: {', '.join(missing)}")

    priority = data.get("priority", "medium")
    if priority and not validate_priority(priority):
        return error_response("Invalid task priority")

    status = data.get("status", "pending")
    if status and not validate_task_status(status):
        return error_response("Invalid task status")

    result = run_shell(
        "shell/schedule/update_task.sh",
        [
            g.current_user["id"],
            data["id"],
            data.get("title", ""),
            data.get("deadline", ""),
            priority,
            data.get("category", ""),
            data.get("repeat_rule", ""),
            data.get("reminder_time", ""),
            data.get("note", ""),
            status,
        ],
        timeout=30,
    )
    return jsonify(result)


@schedule_bp.route("/task/delete", methods=["POST"])
@login_required
def delete_task():
    data = request.get_json(silent=True) or {}

    missing = require_fields(data, ["id"])
    if missing:
        return error_response(f"Missing fields: {', '.join(missing)}")

    result = run_shell("shell/schedule/delete_task.sh", [g.current_user["id"], data["id"]], timeout=30)
    return jsonify(result)
