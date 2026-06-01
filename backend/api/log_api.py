from flask import Blueprint

from services.response_helper import success_response


log_bp = Blueprint("logs", __name__)


@log_bp.route("/ping", methods=["GET"])
def ping():
    return success_response("log api is ready")
