import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def get_bash_command():
    if sys.platform == "win32":
        git_bash_paths = [
            r"D:\software\Git\bin\bash.exe",
            r"C:\Program Files\Git\bin\bash.exe",
            r"C:\Program Files (x86)\Git\bin\bash.exe",
            os.path.expandvars(r"%PROGRAMFILES%\Git\bin\bash.exe"),
        ]
        for path in git_bash_paths:
            if os.path.exists(path):
                return path
        return "bash"
    return "bash"


def run_shell(script_path, args=None, timeout=30):
    args = args or []
    full_script_path = PROJECT_ROOT / script_path

    if not full_script_path.exists():
        return {
            "success": False,
            "message": f"Shell script not found: {script_path}",
            "data": None,
        }

    bash_cmd = get_bash_command()
    command = [bash_cmd, str(full_script_path)] + [str(arg) for arg in args]

    env = os.environ.copy()
    env["DATABASE_PATH"] = str(PROJECT_ROOT / "database" / "campuspilot.db").replace("\\", "/")
    env["PROJECT_ROOT"] = str(PROJECT_ROOT).replace("\\", "/")

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(PROJECT_ROOT),
            env=env,
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
