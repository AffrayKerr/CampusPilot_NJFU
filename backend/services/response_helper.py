from flask import jsonify


def success_response(message="success", data=None):
    return jsonify({
        "success": True,
        "message": message,
        "data": data,
    })


def error_response(message="error", data=None, status_code=400):
    response = jsonify({
        "success": False,
        "message": message,
        "data": data,
    })
    response.status_code = status_code
    return response
