from flask import current_app

from services.db import fetch_all, fetch_one
from services.shell_runner import run_shell


def get_feedback_recipient_emails():
    rows = fetch_all(
        """
        SELECT feedback_email
        FROM admin_settings
        WHERE receive_feedback_email = 1
          AND feedback_email IS NOT NULL
          AND feedback_email != ''
        """
    )
    emails = [row["feedback_email"] for row in rows]

    if emails:
        return emails

    admin_email = current_app.config.get("ADMIN_EMAIL", "")
    if admin_email:
        return [admin_email]

    admins = fetch_all("SELECT email FROM users WHERE role = 'admin' AND email IS NOT NULL AND email != ''")
    return [admin["email"] for admin in admins]


def notify_admin_feedback(feedback_id):
    feedback = fetch_one(
        """
        SELECT feedbacks.id, feedbacks.type, feedbacks.title, feedbacks.priority,
               feedbacks.content, users.username
        FROM feedbacks
        LEFT JOIN users ON users.id = feedbacks.user_id
        WHERE feedbacks.id = ?
        """,
        [feedback_id],
    )
    if not feedback:
        return {"success": False, "message": "Feedback not found", "data": None}

    recipients = get_feedback_recipient_emails()
    if not recipients:
        return {"success": True, "message": "No admin feedback email configured", "data": None}

    subject = f"[CampusPilot反馈] {feedback['title']}"
    content = (
        f"反馈编号：{feedback['id']}\n"
        f"反馈用户：{feedback.get('username') or 'unknown'}\n"
        f"反馈类型：{feedback['type']}\n"
        f"优先级：{feedback['priority']}\n"
        f"内容：{feedback['content']}"
    )

    return run_shell(
        "shell/notification/notify_feedback.sh",
        [subject, content, ",".join(recipients)],
        timeout=30,
    )
