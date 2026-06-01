import json
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def run_shell(script_path, args=None, timeout=30):
    args = args or []
    full_script_path = PROJECT_ROOT / script_path

    if not full_script_path.exists():
        return {
            "success": False,
            "message": f"Shell script not found: {script_path}",
            "data": None,
        }

    command = ["bash", str(full_script_path)] + [str(arg) for arg in args]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(PROJECT_ROOT),
        )
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "message": "Shell script execution timeout",
            "data": None,
        }
    except Exception as exc:
        return {
            "success": False,
            "message": str(exc),
            "data": None,
        }

    stdout = result.stdout.strip()
    stderr = result.stderr.strip()

    if result.returncode != 0:
        return {
            "success": False,
            "message": stderr or "Shell script execution failed",
            "data": {
                "returncode": result.returncode,
                "stdout": stdout,
            },
        }

    if not stdout:
        return {
            "success": True,
            "message": "Shell executed successfully",
            "data": None,
        }

    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError:
        return {
            "success": True,
            "message": "Shell executed successfully",
            "data": stdout,
        }

    return parsed
