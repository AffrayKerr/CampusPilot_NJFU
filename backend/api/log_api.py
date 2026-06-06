from flask import Blueprint, g, request

from services.auth_service import login_required
from services.db import fetch_all
from services.response_helper import error_response, success_response
from utils.validators import validate_log_level, validate_log_module


log_bp = Blueprint("logs", __name__)


def _parse_limit(default=50, maximum=200):
    raw_limit = request.args.get("limit", default)
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        return default
    return max(1, min(limit, maximum))


def _query_logs(user_id, module="", level="", limit=50):
    where_clauses = ["user_id = ?"]
    params = [user_id]

    if module:
        where_clauses.append("module = ?")
        params.append(module)

    if level:
        where_clauses.append("level = ?")
        params.append(level)

    params.append(limit)
    logs = fetch_all(
        f"""
        SELECT id, user_id, module, level, message, detail,
               strftime('%Y-%m-%d %H:%M:%S', created_at) AS created_at
        FROM logs
        WHERE {' AND '.join(where_clauses)}
        ORDER BY id DESC
        LIMIT ?
        """,
        params,
    )
    return success_response("查询成功", {"logs": logs})


@log_bp.route("/ping", methods=["GET"])
def ping():
    return success_response("log api is ready")


@log_bp.route("/list", methods=["GET"])
@login_required
def list_logs():
    module = request.args.get("module", "")
    level = request.args.get("level", "")
    limit = _parse_limit()

    if module and not validate_log_module(module):
        return error_response("Invalid log module")

    if level and not validate_log_level(level):
        return error_response("Invalid log level")

    return _query_logs(g.current_user["id"], module, level, limit)


@log_bp.route("/error", methods=["GET"])
@login_required
def list_error_logs():
    limit = _parse_limit()
    return _query_logs(g.current_user["id"], "", "ERROR", limit)


@log_bp.route("/module/<module>", methods=["GET"])
@login_required
def list_module_logs(module):
    if not validate_log_module(module):
        return error_response("Invalid log module")

    limit = _parse_limit()
    return _query_logs(g.current_user["id"], module, "", limit)
