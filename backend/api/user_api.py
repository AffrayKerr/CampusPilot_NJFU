from flask import Blueprint, jsonify, request

from services.response_helper import error_response, success_response
from services.shell_runner import run_shell
from utils.validators import normalize_bool, require_fields


user_bp = Blueprint("user", __name__)


@user_bp.route("/ping", methods=["GET"])
def ping():
    return success_response("user api is ready")


@user_bp.route("/profile", methods=["GET"])
def get_profile():
    result = run_shell("shell/user/get_profile.sh", timeout=20)
    return jsonify(result)


@user_bp.route("/profile", methods=["POST"])
def update_profile():
    data = request.get_json(silent=True) or {}

    missing = require_fields(data, ["account", "password"])
    if missing:
        return error_response(f"Missing fields: {', '.join(missing)}")

    result = run_shell(
        "shell/user/update_profile.sh",
        [
            data["account"],
            data["password"],
            data.get("email", ""),
            normalize_bool(data.get("enable_email", False)),
            normalize_bool(data.get("enable_desktop", True)),
        ],
        timeout=30,
    )
    return jsonify(result)


@user_bp.route("/export", methods=["POST"])
def export_config():
    data = request.get_json(silent=True) or {}
    export_path = data.get("export_path", "")

    result = run_shell("shell/user/export_config.sh", [export_path], timeout=30)
    return jsonify(result)


@user_bp.route("/import", methods=["POST"])
def import_config():
    data = request.get_json(silent=True) or {}

    missing = require_fields(data, ["import_path"])
    if missing:
        return error_response(f"Missing fields: {', '.join(missing)}")

    result = run_shell("shell/user/import_config.sh", [data["import_path"]], timeout=30)
    return jsonify(result)


@user_bp.route("/statistics", methods=["GET"])
def get_statistics():
    result = run_shell("shell/user/get_statistics.sh", timeout=20)
    return jsonify(result)
