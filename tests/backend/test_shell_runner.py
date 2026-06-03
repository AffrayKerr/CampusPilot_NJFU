import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.shell_runner import run_shell
from utils.validators import require_fields, validate_feedback_type, validate_priority


def test_run_shell_returns_error_when_script_missing():
    result = run_shell("shell/not_exists.sh", timeout=1)

    assert result["success"] is False
    assert "Shell script not found" in result["message"]


def test_require_fields_reports_missing_values():
    data = {"account": "student", "password": ""}
    missing = require_fields(data, ["account", "password", "email"])

    assert missing == ["password", "email"]


def test_basic_validators():
    assert validate_priority("high") is True
    assert validate_priority("wrong") is False
    assert validate_feedback_type("seat") is True
    assert validate_feedback_type("unknown") is False
