from flask import Blueprint

from services.response_helper import success_response


auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/ping", methods=["GET"])
def ping():
    return success_response("auth api is ready")
