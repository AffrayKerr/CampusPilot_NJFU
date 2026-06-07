import json
import re
from datetime import datetime

from flask import Blueprint, g, request

from services.auth_service import login_required
from services.db import execute, fetch_all, fetch_one, init_database
from services.response_helper import error_response, success_response
from utils.validators import normalize_bool, require_fields


reminder_bp = Blueprint("reminder", __name__)

VALID_TARGET_TYPES = ["schedule", "exam", "task"]
TARGET_TABLES = {
    "schedule": "schedules",
    "exam": "exams",
    "task": "tasks",
}
DEFAULT_REMINDER_COLUMNS = {
    "schedule": "schedule_default_reminders",
    "exam": "exam_default_reminders",
    "task": "task_default_reminders",
}
DEFAULT_REMINDERS = {
    "schedule": [15],
    "exam": [1440, 120],
    "task": [1440, 120],
}


@reminder_bp.route("/ping", methods=["GET"])
def ping():
    return success_response("reminder api is ready")


def validate_target_type(target_type):
    return target_type in VALID_TARGET_TYPES


def parse_positive_int(value, field_name):
    try:
        parsed_value = int(value)
    except (TypeError, ValueError):
        return None, f"{field_name} must be a positive integer"
    if parsed_value <= 0:
        return None, f"{field_name} must be a positive integer"
    return parsed_value, None


def parse_reminders_json(value, target_type):
    if not value:
        return DEFAULT_REMINDERS[target_type]
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        return DEFAULT_REMINDERS[target_type]
    if not isinstance(decoded, list):
        return DEFAULT_REMINDERS[target_type]
    reminders = []
    for item in decoded:
        try:
            minutes = int(item)
        except (TypeError, ValueError):
            continue
        if minutes > 0:
            reminders.append(minutes)
    return reminders or DEFAULT_REMINDERS[target_type]


def target_exists(user_id, target_type, target_id):
    table_name = TARGET_TABLES[target_type]
    return fetch_one(
        f"SELECT id FROM {table_name} WHERE id = ? AND user_id = ?",
        [target_id, user_id],
    )



def parse_absolute_datetime(value):
    text = str(value or "").strip().replace("T", " ")
    match = re.search(r"(\d{4}-\d{1,2}-\d{1,2})\s+(\d{1,2}:\d{2})", text)
    if match:
        text = f"{match.group(1)} {match.group(2)}"
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None
@reminder_bp.route("/list", methods=["GET"])
@login_required
def list_reminders():
    init_database()
    target_type = request.args.get("target_type", "")
    params = [g.current_user["id"]]
    query = "SELECT * FROM reminders WHERE user_id = ?"

    if target_type:
        if not validate_target_type(target_type):
            return error_response("Invalid reminder target type")
        query += " AND target_type = ?"
        params.append(target_type)

    query += " ORDER BY target_type ASC, target_id ASC, remind_before_minutes DESC"
    reminders = fetch_all(query, params)
    return success_response("Reminder list", reminders)


@reminder_bp.route("/add", methods=["POST"])
@login_required
def add_reminder():
    init_database()
    data = request.get_json(silent=True) or {}
    missing = require_fields(data, ["target_type", "target_id", "remind_before_minutes"])
    if missing:
        return error_response(f"Missing fields: {', '.join(missing)}")

    target_type = data["target_type"]
    if not validate_target_type(target_type):
        return error_response("Invalid reminder target type")

    target_id, error = parse_positive_int(data["target_id"], "target_id")
    if error:
        return error_response(error)

    remind_before_minutes, error = parse_positive_int(data["remind_before_minutes"], "remind_before_minutes")
    if error:
        return error_response(error)

    if not target_exists(g.current_user["id"], target_type, target_id):
        return error_response("Reminder target not found", status_code=404)

    reminder_id = execute(
        """
        INSERT INTO reminders (user_id, target_type, target_id, remind_before_minutes, enabled)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            g.current_user["id"],
            target_type,
            target_id,
            remind_before_minutes,
            1 if data.get("enabled", True) else 0,
        ],
    )
    reminder = fetch_one("SELECT * FROM reminders WHERE id = ? AND user_id = ?", [reminder_id, g.current_user["id"]])
    return success_response("Reminder added", reminder)


@reminder_bp.route("/update", methods=["POST"])
@login_required
def update_reminder():
    init_database()
    data = request.get_json(silent=True) or {}
    missing = require_fields(data, ["id"])
    if missing:
        return error_response(f"Missing fields: {', '.join(missing)}")

    reminder_id, error = parse_positive_int(data["id"], "id")
    if error:
        return error_response(error)

    reminder = fetch_one("SELECT * FROM reminders WHERE id = ? AND user_id = ?", [reminder_id, g.current_user["id"]])
    if not reminder:
        return error_response("Reminder not found", status_code=404)

    remind_before_minutes = reminder["remind_before_minutes"]
    if "remind_before_minutes" in data:
        remind_before_minutes, error = parse_positive_int(data["remind_before_minutes"], "remind_before_minutes")
        if error:
            return error_response(error)

    enabled = reminder["enabled"]
    if "enabled" in data:
        enabled = 1 if normalize_bool(data["enabled"]) == "true" else 0

    execute(
        """
        UPDATE reminders
        SET remind_before_minutes = ?, enabled = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ? AND user_id = ?
        """,
        [remind_before_minutes, enabled, reminder_id, g.current_user["id"]],
    )
    updated_reminder = fetch_one("SELECT * FROM reminders WHERE id = ? AND user_id = ?", [reminder_id, g.current_user["id"]])
    return success_response("Reminder updated", updated_reminder)


@reminder_bp.route("/delete", methods=["POST"])
@login_required
def delete_reminder():
    init_database()
    data = request.get_json(silent=True) or {}
    missing = require_fields(data, ["id"])
    if missing:
        return error_response(f"Missing fields: {', '.join(missing)}")

    reminder_id, error = parse_positive_int(data["id"], "id")
    if error:
        return error_response(error)

    reminder = fetch_one("SELECT id FROM reminders WHERE id = ? AND user_id = ?", [reminder_id, g.current_user["id"]])
    if not reminder:
        return error_response("Reminder not found", status_code=404)

    execute("DELETE FROM reminders WHERE id = ? AND user_id = ?", [reminder_id, g.current_user["id"]])
    return success_response("Reminder deleted")



@reminder_bp.route("/exam/set-absolute", methods=["POST"])
@login_required
def set_exam_absolute_reminder():
    init_database()
    data = request.get_json(silent=True) or {}
    missing = require_fields(data, ["exam_id", "remind_at"])
    if missing:
        return error_response(f"Missing fields: {', '.join(missing)}")

    exam_id, error = parse_positive_int(data["exam_id"], "exam_id")
    if error:
        return error_response(error)

    exam = fetch_one(
        "SELECT id, exam_time FROM exams WHERE id = ? AND user_id = ?",
        [exam_id, g.current_user["id"]],
    )
    if not exam:
        return error_response("Exam not found", status_code=404)

    exam_dt = parse_absolute_datetime(exam.get("exam_time"))
    remind_dt = parse_absolute_datetime(data.get("remind_at"))
    if not exam_dt:
        return error_response("Exam time cannot be parsed")
    if not remind_dt:
        return error_response("Reminder time must be YYYY-MM-DD HH:mm")

    remind_before_minutes = int((exam_dt - remind_dt).total_seconds() // 60)
    if remind_before_minutes <= 0:
        return error_response("Reminder time must be earlier than exam time")

    execute(
        "DELETE FROM reminders WHERE user_id = ? AND target_type = 'exam' AND target_id = ?",
        [g.current_user["id"], exam_id],
    )
    reminder_id = execute(
        """
        INSERT INTO reminders (user_id, target_type, target_id, remind_before_minutes, enabled)
        VALUES (?, 'exam', ?, ?, 1)
        """,
        [g.current_user["id"], exam_id, remind_before_minutes],
    )
    reminder = fetch_one("SELECT * FROM reminders WHERE id = ?", [reminder_id])
    return success_response("Exam reminder updated", reminder)
@reminder_bp.route("/defaults/apply", methods=["POST"])
@login_required
def apply_default_reminders():
    init_database()
    data = request.get_json(silent=True) or {}
    missing = require_fields(data, ["target_type"])
    if missing:
        return error_response(f"Missing fields: {', '.join(missing)}")

    target_type = data["target_type"]
    if not validate_target_type(target_type):
        return error_response("Invalid reminder target type")

    settings = fetch_one("SELECT * FROM notification_settings WHERE user_id = ?", [g.current_user["id"]]) or {}
    reminder_minutes = parse_reminders_json(settings.get(DEFAULT_REMINDER_COLUMNS[target_type]), target_type)
    targets = fetch_all(f"SELECT id FROM {TARGET_TABLES[target_type]} WHERE user_id = ?", [g.current_user["id"]])

    created_count = 0
    for target in targets:
        for minutes in reminder_minutes:
            existing = fetch_one(
                """
                SELECT id FROM reminders
                WHERE user_id = ? AND target_type = ? AND target_id = ? AND remind_before_minutes = ?
                """,
                [g.current_user["id"], target_type, target["id"], minutes],
            )
            if existing:
                continue
            execute(
                """
                INSERT INTO reminders (user_id, target_type, target_id, remind_before_minutes, enabled)
                VALUES (?, ?, ?, ?, 1)
                """,
                [g.current_user["id"], target_type, target["id"], minutes],
            )
            created_count += 1

    return success_response("Default reminders applied", {"created_count": created_count})


@reminder_bp.route("/trigger", methods=["POST"])
@login_required
def trigger_reminder_check():
    from flask import jsonify

    from services.shell_runner import run_shell

    result = run_shell("shell/schedule/reminder_worker.sh", [g.current_user["id"]], timeout=30)
    return jsonify(result)
