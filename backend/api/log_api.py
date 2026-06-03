from flask import Blueprint, jsonify, request

from services.response_helper import error_response, success_response
from services.shell_runner import run_shell
from utils.validators import validate_log_level, validate_log_module


log_bp = Blueprint("logs", __name__)


@log_bp.route("/ping", methods=["GET"])
def ping():
    return success_response("log api is ready")


@log_bp.route("/list", methods=["GET"])
def list_logs():
    module = request.args.get("module", "")
    level = request.args.get("level", "")
    limit = request.args.get("limit", 50)

    if module and not validate_log_module(module):
        return error_response("Invalid log module")

    if level and not validate_log_level(level):
        return error_response("Invalid log level")

    result = run_shell(
        "shell/system/query_logs.sh",
        [module, level, limit],
        timeout=20,
    )
    return jsonify(result)


@log_bp.route("/error", methods=["GET"])
def list_error_logs():
    limit = request.args.get("limit", 50)
    result = run_shell("shell/system/query_logs.sh", ["error", "ERROR", limit], timeout=20)
    return jsonify(result)


@log_bp.route("/module/<module>", methods=["GET"])
def list_module_logs(module):
    if not validate_log_module(module):
        return error_response("Invalid log module")

    limit = request.args.get("limit", 50)
    result = run_shell("shell/system/query_logs.sh", [module, "", limit], timeout=20)
    return jsonify(result)
