from flask import Blueprint

from services.response_helper import success_response


feedback_bp = Blueprint("feedback", __name__)


@feedback_bp.route("/ping", methods=["GET"])
def ping():
    return success_response("feedback api is ready")
