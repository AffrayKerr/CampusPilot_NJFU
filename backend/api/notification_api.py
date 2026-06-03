from flask import Blueprint, g, jsonify, request

from services.auth_service import login_required
from services.response_helper import error_response, success_response
from services.shell_runner import run_shell
from utils.validators import normalize_bool, require_fields, validate_notification_channel


notification_bp = Blueprint("notification", __name__)


@notification_bp.route("/ping", methods=["GET"])
def ping():
    return success_response("notification api is ready")


@notification_bp.route("/settings", methods=["GET"])
@login_required
def get_settings():
    result = run_shell("shell/notification/get_settings.sh", [g.current_user["id"]], timeout=20)
    return jsonify(result)


@notification_bp.route("/settings", methods=["POST"])
@login_required
def update_settings():
    data = request.get_json(silent=True) or {}

    result = run_shell(
        "shell/notification/update_settings.sh",
        [
            g.current_user["id"],
            normalize_bool(data.get("enable_email", False)),
            normalize_bool(data.get("enable_desktop", True)),
            normalize_bool(data.get("enable_seat_result", True)),
            normalize_bool(data.get("enable_schedule_reminder", True)),
            normalize_bool(data.get("enable_error_alert", True)),
        ],
        timeout=30,
    )
    return jsonify(result)


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
