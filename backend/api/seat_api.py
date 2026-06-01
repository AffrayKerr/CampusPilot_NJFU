from flask import Blueprint

from services.response_helper import success_response


seat_bp = Blueprint("seat", __name__)


@seat_bp.route("/ping", methods=["GET"])
def ping():
    return success_response("seat api is ready")
