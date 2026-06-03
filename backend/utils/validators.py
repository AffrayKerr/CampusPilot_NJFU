def require_fields(data, fields):
    missing = []

    for field in fields:
        if field not in data or data[field] in [None, ""]:
            missing.append(field)

    return missing


def validate_priority(priority):
    return priority in ["high", "medium", "low"]


def validate_feedback_type(feedback_type):
    return feedback_type in [
        "login",
        "schedule",
        "seat",
        "notification",
        "frontend",
        "other",
    ]


def validate_feedback_status(status):
    return status in ["pending", "processing", "resolved", "closed"]


def validate_log_level(level):
    return level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


def validate_log_module(module):
    return module in [
        "auth",
        "schedule",
        "seat",
        "notification",
        "feedback",
        "system",
        "error",
    ]


def validate_task_status(status):
    return status in ["pending", "done", "cancelled"]


def validate_notification_channel(channel):
    return channel in ["email", "desktop", "all"]


def normalize_bool(value):
    if isinstance(value, bool):
        return "true" if value else "false"

    if isinstance(value, int):
        return "true" if value != 0 else "false"

    return str(value).lower()
