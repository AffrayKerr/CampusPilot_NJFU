from services.db import fetch_all
from services.shell_runner import run_shell


def notify_admin_feedback(feedback_id):
    return run_shell("shell/notification/notify_feedback.sh", [feedback_id], timeout=30)
