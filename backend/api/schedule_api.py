from flask import Blueprint

from services.response_helper import success_response


schedule_bp = Blueprint("schedule", __name__)


@schedule_bp.route("/ping", methods=["GET"])
def ping():
    return success_response("schedule api is ready")
