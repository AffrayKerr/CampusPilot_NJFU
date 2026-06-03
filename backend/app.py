from pathlib import Path

from flask import Flask, jsonify, render_template
from flask_cors import CORS

from api.account_api import account_bp
from api.admin_api import admin_bp
from api.auth_api import auth_bp
from api.campus_api import campus_bp
from api.feedback_api import feedback_bp
from api.log_api import log_bp
from api.notification_api import notification_bp
from api.reminder_api import reminder_bp
from api.schedule_api import schedule_bp
from api.seat_api import seat_bp
from api.user_api import user_bp

BASE_DIR = Path(__file__).resolve().parents[1]


def create_app():
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "frontend" / "templates"),
        static_folder=str(BASE_DIR / "frontend" / "static"),
    )

    app.config.from_object("config.Config")
    CORS(app)

    app.register_blueprint(account_bp, url_prefix="/api/account")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")
    app.register_blueprint(campus_bp, url_prefix="/api/campus")
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(schedule_bp, url_prefix="/api/schedule")
    app.register_blueprint(seat_bp, url_prefix="/api/seat")
    app.register_blueprint(log_bp, url_prefix="/api/logs")
    app.register_blueprint(notification_bp, url_prefix="/api/notification")
    app.register_blueprint(reminder_bp, url_prefix="/api/reminder")
    app.register_blueprint(feedback_bp, url_prefix="/api/feedback")
    app.register_blueprint(user_bp, url_prefix="/api/user")

    @app.route("/")
    def index():
        return render_template("login.html")

    @app.route("/dashboard")
    def dashboard():
        return render_template("dashboard.html")

    @app.route("/feedback")
    def feedback():
        return render_template("feedback.html")

    @app.route("/api/health")
    def health():
        return jsonify({"success": True, "message": "CampusPilot backend is running", "data": None})

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(host="0.0.0.0", port=5000, debug=True)
