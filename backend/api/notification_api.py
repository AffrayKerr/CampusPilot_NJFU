from flask import Blueprint

from services.response_helper import success_response


notification_bp = Blueprint("notification", __name__)


@notification_bp.route("/ping", methods=["GET"])
def ping():
    return success_response("notification api is ready")
