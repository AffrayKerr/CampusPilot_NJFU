from flask import Blueprint, g, jsonify, request

from services.auth_service import campus_account_required, login_required
from services.db import execute, init_database
from services.response_helper import error_response, success_response
from services.shell_runner import run_shell
from utils.validators import require_fields, validate_priority, validate_task_status


schedule_bp = Blueprint("schedule", __name__)


@schedule_bp.route("/ping", methods=["GET"])
def ping():
    return success_response("schedule api is ready")


@schedule_bp.route("/sync", methods=["POST"])
@campus_account_required
def sync_schedule():
    result = run_shell("shell/schedule/sync_schedule.sh", [g.current_user["id"]], timeout=120)
    return jsonify(result)


@schedule_bp.route("/exam/sync", methods=["POST"])
@campus_account_required
def sync_exam():
    result = run_shell("shell/schedule/sync_exam.sh", [g.current_user["id"]], timeout=150)
    return jsonify(result)


@schedule_bp.route("/today", methods=["GET"])
@login_required
def list_today():
    result = run_shell("shell/schedule/list_today.sh", [g.current_user["id"]], timeout=30)
    return jsonify(result)


@schedule_bp.route("/next-week", methods=["GET"])
@login_required
def list_next_week():
    result = run_shell("shell/schedule/list_next_week.sh", [g.current_user["id"]], timeout=30)
    return jsonify(result)


@schedule_bp.route("/changes/detect", methods=["POST"])
@campus_account_required
def detect_changes():
    result = run_shell("shell/schedule/detect_changes.sh", [g.current_user["id"]], timeout=120)
    return jsonify(result)


@schedule_bp.route("/task/add", methods=["POST"])
@login_required
def add_task():
    init_database()
    data = request.get_json(silent=True) or {}

    missing = require_fields(data, ["title", "deadline"])
    if missing:
        return error_response(f"Missing fields: {', '.join(missing)}")

    priority = data.get("priority", "medium")
    if not validate_priority(priority):
        return error_response("Invalid task priority")

    reminder_minutes = data.get("remind_before_minutes", data.get("reminder_minutes"))
    if reminder_minutes in ["", None]:
        reminder_minutes = None
    else:
        try:
            reminder_minutes = int(reminder_minutes)
        except (TypeError, ValueError):
            return error_response("Invalid reminder minutes")
        if reminder_minutes <= 0:
            return error_response("Invalid reminder minutes")

    task_id = execute(
        """
        INSERT INTO tasks (user_id, title, deadline, priority, category, repeat_rule, reminder_time, note, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')
        """,
        [
            g.current_user["id"],
            data["title"].strip(),
            data["deadline"],
            priority,
            data.get("category", ""),
            data.get("repeat_rule", "none"),
            data.get("reminder_time", ""),
            data.get("note", ""),
        ],
    )

    if reminder_minutes is not None:
        execute(
            """
            INSERT INTO reminders (user_id, target_type, target_id, remind_before_minutes, enabled)
            VALUES (?, 'task', ?, ?, 1)
            """,
            [g.current_user["id"], task_id, reminder_minutes],
        )

    return success_response(
        "task added",
        {
            "task_id": task_id,
            "title": data["title"].strip(),
            "remind_before_minutes": reminder_minutes,
        },
    )

@schedule_bp.route("/task/update", methods=["POST"])
@login_required
def update_task():
    data = request.get_json(silent=True) or {}

    missing = require_fields(data, ["id"])
    if missing:
        return error_response(f"Missing fields: {', '.join(missing)}")

    priority = data.get("priority")
    if priority and not validate_priority(priority):
        return error_response("Invalid task priority")

    status = data.get("status")
    if status and not validate_task_status(status):
        return error_response("Invalid task status")

    fields = []
    params = []
    for field in ["title", "deadline", "category", "repeat_rule", "reminder_time", "note"]:
        if field in data:
            fields.append(f"{field} = ?")
            params.append(data.get(field, ""))
    if priority:
        fields.append("priority = ?")
        params.append(priority)
    if status:
        fields.append("status = ?")
        params.append(status)

    if not fields:
        return error_response("No fields to update")

    fields.append("updated_at = CURRENT_TIMESTAMP")
    params.extend([data["id"], g.current_user["id"]])
    task_id = execute(
        f"UPDATE tasks SET {', '.join(fields)} WHERE id = ? AND user_id = ?",
        params,
    )

    if status in {"done", "cancelled"}:
        execute(
            "UPDATE reminders SET enabled = 0, updated_at = CURRENT_TIMESTAMP WHERE user_id = ? AND target_type = 'task' AND target_id = ?",
            [g.current_user["id"], data["id"]],
        )

    return success_response("task updated", {"task_id": data["id"], "updated": task_id})

@schedule_bp.route("/task/delete", methods=["POST"])
@login_required
def delete_task():
    data = request.get_json(silent=True) or {}

    missing = require_fields(data, ["id"])
    if missing:
        return error_response(f"Missing fields: {', '.join(missing)}")

    result = run_shell("shell/schedule/delete_task.sh", [g.current_user["id"], data["id"]], timeout=30)
    return jsonify(result)
