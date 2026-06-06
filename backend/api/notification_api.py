import json

from flask import Blueprint, g, jsonify, request

from services.auth_service import login_required
from services.db import execute, fetch_one, init_database
from services.response_helper import error_response, success_response
from services.shell_runner import run_shell
from utils.validators import normalize_bool, require_fields, validate_notification_channel


notification_bp = Blueprint("notification", __name__)

DEFAULT_SCHEDULE_REMINDERS = [15]
DEFAULT_EXAM_REMINDERS = [1440, 120]
DEFAULT_TASK_REMINDERS = [1440, 120]


@notification_bp.route("/ping", methods=["GET"])
def ping():
    return success_response("notification api is ready")


def validate_reminder_minutes_list(value, default_value):
    if value in [None, ""]:
        return default_value, None
    if not isinstance(value, list):
        return None, "Reminder settings must be arrays"

    reminders = []
    for item in value:
        try:
            minutes = int(item)
        except (TypeError, ValueError):
            return None, "Reminder minutes must be positive integers"
        if minutes <= 0:
            return None, "Reminder minutes must be positive integers"
        reminders.append(minutes)
    return reminders, None


def decode_reminders(value, default_value):
    if not value:
        return default_value
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        return default_value
    if not isinstance(decoded, list):
        return default_value
    return decoded


def ensure_notification_settings(user_id):
    init_database()
    settings = fetch_one("SELECT * FROM notification_settings WHERE user_id = ?", [user_id])
    if settings:
        return settings

    execute(
        """
        INSERT INTO notification_settings (
            user_id,
            enable_email,
            enable_desktop,
            enable_seat_result,
            enable_schedule_reminder,
            enable_error_alert,
            schedule_default_reminders,
            exam_default_reminders,
            task_default_reminders
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            user_id,
            0,
            1,
            1,
            1,
            1,
            json.dumps(DEFAULT_SCHEDULE_REMINDERS),
            json.dumps(DEFAULT_EXAM_REMINDERS),
            json.dumps(DEFAULT_TASK_REMINDERS),
        ],
    )
    return fetch_one("SELECT * FROM notification_settings WHERE user_id = ?", [user_id])


def format_settings(settings):
    return {
        "enable_email": bool(settings.get("enable_email")),
        "enable_desktop": bool(settings.get("enable_desktop")),
        "enable_seat_result": bool(settings.get("enable_seat_result")),
        "enable_schedule_reminder": bool(settings.get("enable_schedule_reminder")),
        "enable_error_alert": bool(settings.get("enable_error_alert")),
        "schedule_default_reminders": decode_reminders(
            settings.get("schedule_default_reminders"), DEFAULT_SCHEDULE_REMINDERS
        ),
        "exam_default_reminders": decode_reminders(settings.get("exam_default_reminders"), DEFAULT_EXAM_REMINDERS),
        "task_default_reminders": decode_reminders(settings.get("task_default_reminders"), DEFAULT_TASK_REMINDERS),
    }


@notification_bp.route("/settings", methods=["GET"])
@login_required
def get_settings():
    settings = ensure_notification_settings(g.current_user["id"])
    return success_response("Notification settings", format_settings(settings))


@notification_bp.route("/settings", methods=["POST"])
@login_required
def update_settings():
    data = request.get_json(silent=True) or {}
    settings = ensure_notification_settings(g.current_user["id"])

    schedule_reminders, error = validate_reminder_minutes_list(
        data.get("schedule_default_reminders"),
        decode_reminders(settings.get("schedule_default_reminders"), DEFAULT_SCHEDULE_REMINDERS),
    )
    if error:
        return error_response(error)

    exam_reminders, error = validate_reminder_minutes_list(
        data.get("exam_default_reminders"),
        decode_reminders(settings.get("exam_default_reminders"), DEFAULT_EXAM_REMINDERS),
    )
    if error:
        return error_response(error)

    task_reminders, error = validate_reminder_minutes_list(
        data.get("task_default_reminders"),
        decode_reminders(settings.get("task_default_reminders"), DEFAULT_TASK_REMINDERS),
    )
    if error:
        return error_response(error)

    execute(
        """
        UPDATE notification_settings
        SET enable_email = ?,
            enable_desktop = ?,
            enable_seat_result = ?,
            enable_schedule_reminder = ?,
            enable_error_alert = ?,
            schedule_default_reminders = ?,
            exam_default_reminders = ?,
            task_default_reminders = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE user_id = ?
        """,
        [
            1 if data.get("enable_email", settings.get("enable_email", 0)) else 0,
            1 if data.get("enable_desktop", settings.get("enable_desktop", 1)) else 0,
            1 if data.get("enable_seat_result", settings.get("enable_seat_result", 1)) else 0,
            1 if data.get("enable_schedule_reminder", settings.get("enable_schedule_reminder", 1)) else 0,
            1 if data.get("enable_error_alert", settings.get("enable_error_alert", 1)) else 0,
            json.dumps(schedule_reminders),
            json.dumps(exam_reminders),
            json.dumps(task_reminders),
            g.current_user["id"],
        ],
    )
    updated_settings = ensure_notification_settings(g.current_user["id"])
    return success_response("Notification settings updated", format_settings(updated_settings))


@notification_bp.route("/test", methods=["POST"])
@login_required
def test_notification():
    data = request.get_json(silent=True) or {}

    channel = data.get("channel", "all")
    if not validate_notification_channel(channel):
        return error_response("Invalid notification channel")

    result = run_shell(
        "shell/notification/test_notify.sh",
        [
            g.current_user["id"],
            channel,
            data.get("title", "CampusPilot 测试通知"),
            data.get("content", "通知功能测试成功"),
        ],
        timeout=30,
    )
    return jsonify(result)


@notification_bp.route("/email", methods=["POST"])
@login_required
def send_email():
    data = request.get_json(silent=True) or {}

    missing = require_fields(data, ["subject", "content"])
    if missing:
        return error_response(f"Missing fields: {', '.join(missing)}")

    result = run_shell(
        "shell/notification/notify_email.sh",
        [
            g.current_user["id"],
            data["subject"],
            data["content"],
            data.get("to", ""),
        ],
        timeout=30,
    )
    return jsonify(result)


@notification_bp.route("/desktop", methods=["POST"])
@login_required
def send_desktop():
    data = request.get_json(silent=True) or {}

    missing = require_fields(data, ["title", "content"])
    if missing:
        return error_response(f"Missing fields: {', '.join(missing)}")

    result = run_shell(
        "shell/notification/notify_desktop.sh",
        [
            g.current_user["id"],
            data["title"],
            data["content"],
        ],
        timeout=20,
    )
    return jsonify(result)


@notification_bp.route("/daily-summary", methods=["POST"])
@login_required
def daily_summary():
    result = run_shell(
        "shell/notification/daily_summary.sh",
        [g.current_user["id"]],
        timeout=30,
    )
    return jsonify(result)
