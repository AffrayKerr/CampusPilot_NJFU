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
        timeout=30,
    )
    return jsonify(result)


@auth_bp.route("/interactive-status", methods=["GET"])
@campus_account_required
def interactive_status():
    import os

    user_id = str(g.current_user["id"])
    runtime_base = os.environ.get("USERS_RUNTIME_DIR") or os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "runtime", "users")
    )
    user_dir = os.path.join(runtime_base, user_id)
    pid_file = os.path.join(user_dir, "selenium_login.pid")
    status_file = os.path.join(user_dir, "selenium_login.status")

    in_progress = False
    if os.path.isfile(pid_file):
        try:
            pid = int(open(pid_file).read().strip())
            in_progress = _pid_alive(pid)
        except (OSError, ValueError):
            pass

    status_content = None
    if os.path.isfile(status_file):
        try:
            status_content = open(status_file, encoding="utf-8").read().strip()
        except OSError:
            pass

    if status_content and status_content.startswith("{"):
        import json as _json
        try:
            parsed = _json.loads(status_content)
            parsed["data"] = parsed.get("data") or {}
            if parsed.get("success"):
                parsed["data"]["status"] = "completed"
            else:
                parsed["data"]["status"] = "failed"
            return jsonify(parsed)
        except _json.JSONDecodeError:
            pass

    if status_content in {"starting", "in_progress"} and in_progress:
        return jsonify({
            "success": True,
            "message": "Browser login in progress, please complete login in the browser window",
            "data": {"status": "in_progress"},
        })

    if in_progress:
        return jsonify({
            "success": True,
            "message": "Browser login in progress, please complete login in the browser window",
            "data": {"status": "in_progress"},
        })

    result = run_shell("shell/auth/check_session.sh", [g.current_user["id"]], timeout=20)
    if result.get("success"):
        result.setdefault("data", {})
        result["data"]["status"] = "completed"
    else:
        result["data"] = {"status": "idle"}
    return jsonify(result)


def _pid_alive(pid: int) -> bool:
    try:
        import os
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


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
