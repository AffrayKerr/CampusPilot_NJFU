from flask import Blueprint, g, jsonify

from services.auth_service import login_required
from services.response_helper import success_response
from services.shell_runner import run_shell


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/ping", methods=["GET"])
def ping():
    return success_response("auth api is ready")


@auth_bp.route("/login", methods=["POST"])
@login_required
def login():
    result = run_shell(
        "shell/auth/login_bound.sh",
        [g.current_user["id"]],
        timeout=60,
    )
    return jsonify(result)


@auth_bp.route("/status", methods=["GET"])
@login_required
def status():
    result = run_shell("shell/auth/check_session.sh", [g.current_user["id"]], timeout=20)
    return jsonify(result)


@auth_bp.route("/refresh", methods=["POST"])
@login_required
def refresh():
    result = run_shell("shell/auth/refresh_session.sh", [g.current_user["id"]], timeout=60)
    return jsonify(result)


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    result = run_shell("shell/auth/logout.sh", [g.current_user["id"]], timeout=30)
    return jsonify(result)
