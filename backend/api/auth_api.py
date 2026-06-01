from flask import Blueprint, jsonify, request

from services.response_helper import error_response, success_response
from services.shell_runner import run_shell
from utils.validators import require_fields


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/ping", methods=["GET"])
def ping():
    return success_response("auth api is ready")


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}

    missing = require_fields(data, ["account", "password"])
    if missing:
        return error_response(f"Missing fields: {', '.join(missing)}")

    result = run_shell(
        "shell/auth/login.sh",
        [
            data["account"],
            data["password"],
            data.get("email", ""),
        ],
        timeout=60,
    )
    return jsonify(result)


@auth_bp.route("/status", methods=["GET"])
def status():
    result = run_shell("shell/auth/check_session.sh", timeout=20)
    return jsonify(result)


@auth_bp.route("/refresh", methods=["POST"])
def refresh():
    result = run_shell("shell/auth/refresh_session.sh", timeout=60)
    return jsonify(result)


@auth_bp.route("/logout", methods=["POST"])
def logout():
    result = run_shell("shell/auth/logout.sh", timeout=30)
    return jsonify(result)
