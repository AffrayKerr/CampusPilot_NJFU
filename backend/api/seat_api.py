import json
from datetime import datetime

from flask import Blueprint, g, jsonify, request

from services.auth_service import campus_account_required
from services.response_helper import error_response, success_response
from services.shell_runner import run_shell
from utils.validators import normalize_bool, require_fields


seat_bp = Blueprint("seat", __name__)

MIN_RESERVE_MINUTES = 120
REGULAR_CLOSE_TIME = "22:00"
FRIDAY_CLOSE_TIME = "20:00"
OPEN_TIME = "07:30"


@seat_bp.route("/ping", methods=["GET"])
def ping():
    return success_response("seat api is ready")


def parse_date(date_text):
    try:
        return datetime.strptime(date_text, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def parse_time(time_text):
    try:
        return datetime.strptime(time_text, "%H:%M").time()
    except (TypeError, ValueError):
        return None


def minutes_since_midnight(time_value):
    return time_value.hour * 60 + time_value.minute


def get_library_close_time(reserve_date):
    if reserve_date.weekday() == 4:
        return FRIDAY_CLOSE_TIME
    return REGULAR_CLOSE_TIME


def normalize_reserve_time_slots(data):
    slots = data.get("reserve_time_slots")
    if slots in [None, ""]:
        start_time = data.get("reserve_start_time", "")
        end_time = data.get("reserve_end_time", "")
        if not start_time and not end_time:
            return []
        slots = [{"start_time": start_time, "end_time": end_time}]

    if not isinstance(slots, list):
        return None

    normalized_slots = []
    for slot in slots:
        if not isinstance(slot, dict):
            return None
        normalized_slots.append(
            {
                "start_time": slot.get("start_time", ""),
                "end_time": slot.get("end_time", ""),
            }
        )
    return normalized_slots


def validate_reserve_time_slots(data):
    reserve_date_text = data.get("reserve_date", "")
    slots = normalize_reserve_time_slots(data)

    if slots is None:
        return None, "Invalid reserve time slots"

    if not slots:
        return [], None

    reserve_date = parse_date(reserve_date_text)
    if not reserve_date:
        return None, "Invalid reserve date"

    open_time = parse_time(OPEN_TIME)
    close_time_text = get_library_close_time(reserve_date)
    close_time = parse_time(close_time_text)
    open_minutes = minutes_since_midnight(open_time)
    close_minutes = minutes_since_midnight(close_time)

    for slot in slots:
        start_time = parse_time(slot["start_time"])
        end_time = parse_time(slot["end_time"])
        if not start_time or not end_time:
            return None, "Invalid reserve time format"

        start_minutes = minutes_since_midnight(start_time)
        end_minutes = minutes_since_midnight(end_time)
        duration_minutes = end_minutes - start_minutes

        if start_minutes < open_minutes or end_minutes > close_minutes:
            return None, f"Reserve time must be between {OPEN_TIME} and {close_time_text}"

        if duration_minutes < MIN_RESERVE_MINUTES:
            return None, "Each reserve time slot must be at least 2 hours"

    return slots, None


def build_seat_config_args(data):
    slots, validation_error = validate_reserve_time_slots(data)
    if validation_error:
        return None, validation_error

    reserve_time_slots_json = json.dumps(slots, ensure_ascii=False)
    first_slot = slots[0] if slots else {}
    reserve_start_time = data.get("reserve_start_time", first_slot.get("start_time", ""))
    reserve_end_time = data.get("reserve_end_time", first_slot.get("end_time", ""))

    return [
        data.get("floor", ""),
        data["seat_no"],
        data.get("priority", 1),
        data.get("reserve_date", ""),
        reserve_start_time,
        reserve_end_time,
        data.get("check_start_time", ""),
        data.get("check_stop_time", ""),
        data.get("retry_interval", 10),
        data.get("max_retry_count", 30),
        data.get("max_duration_minutes", 15),
        normalize_bool(data.get("enabled", True)),
        reserve_time_slots_json,
    ], None


@seat_bp.route("/config", methods=["POST"])
@campus_account_required
def save_config():
    data = request.get_json(silent=True) or {}

    missing = require_fields(data, ["seat_no"])
    if missing:
        return error_response(f"Missing fields: {', '.join(missing)}")

    args, validation_error = build_seat_config_args(data)
    if validation_error:
        return error_response(validation_error)

    result = run_shell(
        "shell/seat/seat_config.sh",
        [g.current_user["id"], *args],
        timeout=30,
    )
    return jsonify(result)


@seat_bp.route("/config/list", methods=["GET"])
@campus_account_required
def list_configs():
    result = run_shell("shell/seat/list_configs.sh", [g.current_user["id"]], timeout=20)
    return jsonify(result)


@seat_bp.route("/config/update", methods=["POST"])
@campus_account_required
def update_config():
    data = request.get_json(silent=True) or {}

    missing = require_fields(data, ["id", "seat_no"])
    if missing:
        return error_response(f"Missing fields: {', '.join(missing)}")

    args, validation_error = build_seat_config_args(data)
    if validation_error:
        return error_response(validation_error)

    result = run_shell(
        "shell/seat/update_config.sh",
        [g.current_user["id"], data["id"], *args],
        timeout=30,
    )
    return jsonify(result)


@seat_bp.route("/config/delete", methods=["POST"])
@campus_account_required
def delete_config():
    data = request.get_json(silent=True) or {}

    missing = require_fields(data, ["id"])
    if missing:
        return error_response(f"Missing fields: {', '.join(missing)}")

    result = run_shell("shell/seat/delete_config.sh", [g.current_user["id"], data["id"]], timeout=30)
    return jsonify(result)


@seat_bp.route("/check", methods=["GET"])
@campus_account_required
def check_seat():
    floor = request.args.get("floor", "")
    seat_no = request.args.get("seat_no", "")

    result = run_shell("shell/seat/check_seat.sh", [g.current_user["id"], floor, seat_no], timeout=30)
    return jsonify(result)


@seat_bp.route("/reserve", methods=["POST"])
@campus_account_required
def reserve_seat():
    data = request.get_json(silent=True) or {}

    missing = require_fields(data, ["seat_no"])
    if missing:
        return error_response(f"Missing fields: {', '.join(missing)}")

    slots, validation_error = validate_reserve_time_slots(data)
    if validation_error:
        return error_response(validation_error)

    reserve_time_slots_json = json.dumps(slots, ensure_ascii=False)
    first_slot = slots[0] if slots else {}
    reserve_start_time = data.get("reserve_start_time", first_slot.get("start_time", ""))
    reserve_end_time = data.get("reserve_end_time", first_slot.get("end_time", ""))

    result = run_shell(
        "shell/seat/reserve_seat.sh",
        [
            g.current_user["id"],
            data["seat_no"],
            data.get("floor", ""),
            data.get("reserve_date", ""),
            reserve_start_time,
            reserve_end_time,
            reserve_time_slots_json,
        ],
        timeout=60,
    )
    return jsonify(result)


@seat_bp.route("/start", methods=["POST"])
@campus_account_required
def start_worker():
    result = run_shell("shell/seat/start_worker.sh", [g.current_user["id"]], timeout=30)
    return jsonify(result)


@seat_bp.route("/stop", methods=["POST"])
@campus_account_required
def stop_worker():
    result = run_shell("shell/seat/stop_worker.sh", [g.current_user["id"]], timeout=30)
    return jsonify(result)


@seat_bp.route("/status", methods=["GET"])
@campus_account_required
def worker_status():
    result = run_shell("shell/seat/worker_status.sh", [g.current_user["id"]], timeout=20)
    return jsonify(result)


@seat_bp.route("/retry", methods=["POST"])
@campus_account_required
def retry_seat():
    result = run_shell("shell/seat/retry_seat.sh", [g.current_user["id"]], timeout=120)
    return jsonify(result)


@seat_bp.route("/cancel", methods=["POST"])
@campus_account_required
def cancel_seat():
    data = request.get_json(silent=True) or {}
    seat_no = data.get("seat_no", "")

    result = run_shell("shell/seat/cancel_seat.sh", [g.current_user["id"], seat_no], timeout=30)
    return jsonify(result)


@seat_bp.route("/result", methods=["GET"])
@campus_account_required
def list_results():
    limit = request.args.get("limit", 20)
    result = run_shell("shell/seat/list_results.sh", [g.current_user["id"], limit], timeout=20)
    return jsonify(result)
