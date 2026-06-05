from flask import Blueprint, g, jsonify

from services.auth_service import campus_account_required
from services.response_helper import success_response
from services.shell_runner import run_shell


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/ping", methods=["GET"])
def ping():
    return success_response("auth api is ready")


@auth_bp.route("/login", methods=["POST"])
@campus_account_required
def login():
    result = run_shell(
        "shell/auth/login_bound.sh",
        [g.current_user["id"]],
        timeout=60,
    )
    return jsonify(result)


@auth_bp.route("/status", methods=["GET"])
@campus_account_required
def status():
    result = run_shell("shell/auth/check_session.sh", [g.current_user["id"]], timeout=20)
    return jsonify(result)


@auth_bp.route("/refresh", methods=["POST"])
@campus_account_required
def refresh():
    result = run_shell("shell/auth/refresh_session.sh", [g.current_user["id"]], timeout=60)
    return jsonify(result)


@auth_bp.route("/logout", methods=["POST"])
@campus_account_required
def logout():
    result = run_shell("shell/auth/logout.sh", [g.current_user["id"]], timeout=30)
    return jsonify(result)


@auth_bp.route("/bind-interactive", methods=["POST"])
@campus_account_required
def bind_interactive():
    result = run_shell(
        "shell/auth/bind_webvpn_interactive.sh",
        [g.current_user["id"]],
        timeout=600,
    )
    return jsonify(result)


@auth_bp.route("/keep-alive", methods=["POST"])
@campus_account_required
def keep_alive():
    result = run_shell(
        "shell/auth/session_keeper.sh",
        [g.current_user["id"]],
        timeout=60,
    )
    return jsonify(result)


@auth_bp.route("/relogin-status", methods=["GET"])
@campus_account_required
def relogin_status():
    import os
    from services.db import fetch_one

    user = g.current_user
    runtime_dir = os.environ.get("USERS_RUNTIME_DIR") or os.path.join(
        os.path.dirname(__file__), "..", "..", "runtime", "users"
    )
    flag_path = os.path.join(runtime_dir, str(user["id"]), "needs_relogin")
    flag_path = os.path.normpath(flag_path)

    needs_relogin = os.path.isfile(flag_path)
    flagged_at = None
    if needs_relogin:
        try:
            with open(flag_path, encoding="utf-8") as f:
                flagged_at = f.read().strip()
        except OSError:
            pass

    account = fetch_one(
        "SELECT session_valid FROM campus_accounts WHERE user_id = ?",
        [user["id"]],
    )
    session_valid = bool(account and account["session_valid"]) if account else False

    return jsonify({
        "success": True,
        "message": "Relogin status",
        "data": {
            "needs_relogin": needs_relogin,
            "session_valid": session_valid,
            "flagged_at": flagged_at,
        },
    })
