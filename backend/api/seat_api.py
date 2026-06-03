from flask import Blueprint, g, jsonify, request

from services.auth_service import campus_account_required
from services.response_helper import error_response, success_response
from services.shell_runner import run_shell
from utils.validators import normalize_bool, require_fields


seat_bp = Blueprint("seat", __name__)


@seat_bp.route("/ping", methods=["GET"])
def ping():
    return success_response("seat api is ready")


def build_seat_config_args(data):
    return [
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
    ]


@seat_bp.route("/config", methods=["POST"])
@campus_account_required
def save_config():
    data = request.get_json(silent=True) or {}

    missing = require_fields(data, ["seat_no"])
    if missing:
        return error_response(f"Missing fields: {', '.join(missing)}")

    result = run_shell(
        "shell/seat/seat_config.sh",
        [g.current_user["id"], *build_seat_config_args(data)],
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

    result = run_shell(
        "shell/seat/update_config.sh",
        [g.current_user["id"], data["id"], *build_seat_config_args(data)],
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

    result = run_shell(
        "shell/seat/reserve_seat.sh",
        [
            g.current_user["id"],
            data["seat_no"],
            data.get("reserve_date", ""),
            data.get("reserve_start_time", ""),
            data.get("reserve_end_time", ""),
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
