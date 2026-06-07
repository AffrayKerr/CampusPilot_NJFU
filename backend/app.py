import os
import threading
import time
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
from services.db import fetch_all, init_database
from services.shell_runner import run_shell

_reminder_scheduler_started = False


def start_reminder_scheduler(app):
    global _reminder_scheduler_started
    if _reminder_scheduler_started:
        return
    if os.environ.get("CAMPUSPILOT_DISABLE_REMINDER_SCHEDULER") == "1":
        return
    if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return

    _reminder_scheduler_started = True

    def worker_loop():
        time.sleep(5)
        while True:
            try:
                with app.app_context():
                    init_database()
                    users = fetch_all(
                        """
                        SELECT DISTINCT u.id
                        FROM users u
                        JOIN reminders r ON r.user_id = u.id
                        WHERE r.enabled = 1
                        """
                    )
                for user in users:
                    run_shell("shell/schedule/reminder_worker.sh", [user["id"]], timeout=60)
            except Exception:
                app.logger.exception("reminder scheduler failed")
            time.sleep(60)

    threading.Thread(target=worker_loop, daemon=True, name="reminder-scheduler").start()

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

    start_reminder_scheduler(app)

    @app.route("/")
    def index():
        return render_template("login.html")

    @app.route("/dashboard")
    def dashboard():
        return render_template("dashboard.html")

    @app.route("/schedule")
    def schedule():
        return render_template("schedule.html")

    @app.route("/tasks")
    def tasks():
        return render_template("tasks.html")

    @app.route("/seat")
    def seat():
        return render_template("seat.html")

    @app.route("/logs")
    def logs():
        return render_template("logs.html")

    @app.route("/profile")
    def profile():
        return render_template("profile.html")

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
