from flask import Blueprint, jsonify, request

from services.response_helper import error_response, success_response
from services.shell_runner import run_shell
from utils.validators import normalize_bool, require_fields


seat_bp = Blueprint("seat", __name__)


@seat_bp.route("/ping", methods=["GET"])
def ping():
    return success_response("seat api is ready")


@seat_bp.route("/config", methods=["POST"])
def save_config():
    data = request.get_json(silent=True) or {}

    missing = require_fields(data, ["seat_no"])
    if missing:
        return error_response(f"Missing fields: {', '.join(missing)}")

    result = run_shell(
        "shell/seat/seat_config.sh",
        [
            data.get("floor", ""),
            data["seat_no"],
            data.get("priority", 1),
            data.get("reserve_date", ""),
            data.get("reserve_start_time", ""),
            data.get("reserve_end_time", ""),
            data.get("check_start_time", ""),
            data.get("check_stop_time", ""),
            data.get("retry_interval", 10),
            data.get("max_retry_count", 30),
            data.get("max_duration_minutes", 15),
            normalize_bool(data.get("enabled", True)),
        ],
        timeout=30,
    )
    return jsonify(result)


@seat_bp.route("/check", methods=["GET"])
def check_seat():
    floor = request.args.get("floor", "")
    seat_no = request.args.get("seat_no", "")

    result = run_shell("shell/seat/check_seat.sh", [floor, seat_no], timeout=30)
    return jsonify(result)


@seat_bp.route("/reserve", methods=["POST"])
def reserve_seat():
    data = request.get_json(silent=True) or {}

    missing = require_fields(data, ["seat_no"])
    if missing:
        return error_response(f"Missing fields: {', '.join(missing)}")

    result = run_shell(
        "shell/seat/reserve_seat.sh",
        [
            data["seat_no"],
            data.get("reserve_date", ""),
            data.get("reserve_start_time", ""),
            data.get("reserve_end_time", ""),
        ],
        timeout=60,
    )
    return jsonify(result)


@seat_bp.route("/start", methods=["POST"])
def start_worker():
    result = run_shell("shell/seat/seat_worker.sh", timeout=120)
    return jsonify(result)


@seat_bp.route("/retry", methods=["POST"])
def retry_seat():
    result = run_shell("shell/seat/retry_seat.sh", timeout=120)
    return jsonify(result)


@seat_bp.route("/cancel", methods=["POST"])
def cancel_seat():
    data = request.get_json(silent=True) or {}
    seat_no = data.get("seat_no", "")

    result = run_shell("shell/seat/cancel_seat.sh", [seat_no], timeout=30)
    return jsonify(result)


@seat_bp.route("/result", methods=["GET"])
def list_results():
    limit = request.args.get("limit", 20)
    result = run_shell("shell/seat/list_results.sh", [limit], timeout=20)
    return jsonify(result)
