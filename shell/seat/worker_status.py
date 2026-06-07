#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any

NOISY_MESSAGES = {
    "Seat worker started",
    "Seat worker stopped",
    "Worker preparing library token",
    "Worker library token ready",
    "Seat config saved",
    "Seat config updated",
    "Seat config deleted",
}

RUN_MESSAGE_PREFIXES = (
    "Worker error",
    "Worker gave up",
    "Worker finished",
    "Worker waiting",
    "Worker trying",
    "Worker reserved",
    "Worker max duration",
    "Worker reservation/check window ended",
    "Reservation error",
    "Retry error",
    "Retry succeeded",
    "Seat reserved",
    "Seat worker started",
    "Seat worker stopped",
    "Worker preparing library token",
    "Worker library token ready",
)


def emit(success: bool, message: str, data: Any = None) -> None:
    print(json.dumps({"success": success, "message": message, "data": data}, ensure_ascii=False))


def normalize_path(path_text: str) -> Path:
    text = str(path_text)
    if os.name == "nt" and len(text) >= 3 and text[0] == "/" and text[2] == "/" and text[1].isalpha():
        text = f"{text[1]}:{text[2:]}"
    return Path(text)


def pid_is_running(pid_text: str) -> bool:
    try:
        pid = int(str(pid_text).strip())
    except Exception:
        return False
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return str(pid) in result.stdout
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return False


def row_to_json(row: sqlite3.Row | None) -> str:
    return json.dumps(dict(row), ensure_ascii=False) if row else ""


def is_run_message(message: str) -> bool:
    return any(message.startswith(prefix) for prefix in RUN_MESSAGE_PREFIXES)


def latest_db_log(db_path: Path, user_id: str) -> str:
    if not db_path.is_file():
        return ""
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, level, module, message, detail, created_at
            FROM logs
            WHERE module = 'seat' AND (user_id = ? OR CAST(user_id AS TEXT) = ?)
            ORDER BY id DESC
            LIMIT 100
            """,
            (user_id, user_id),
        ).fetchall()
        conn.close()
        if not rows:
            return ""
        for row in rows:
            if is_run_message(str(row["message"])):
                return row_to_json(row)
        for row in rows:
            if row["message"] not in NOISY_MESSAGES:
                return row_to_json(row)
        return row_to_json(rows[0])
    except Exception:
        return ""


def latest_runtime_log(path: Path) -> str:
    if not path.is_file():
        return ""
    latest = ""
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
            except Exception:
                continue
            message = str(item.get("message") or "")
            if item.get("module") == "seat" and (is_run_message(message) or message not in NOISY_MESSAGES):
                latest = json.dumps(item, ensure_ascii=False)
    except Exception:
        return ""
    return latest


def latest_worker_output(path: Path) -> str:
    if not path.is_file():
        return ""
    latest = ""
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.strip():
                latest = line.strip()
    except Exception:
        return ""
    return latest


def main() -> None:
    if len(sys.argv) < 7:
        emit(False, "Missing worker status arguments", None)
        raise SystemExit(1)

    db_path = normalize_path(sys.argv[1])
    user_id = sys.argv[2]
    pid_file = normalize_path(sys.argv[3])
    lock_file = normalize_path(sys.argv[4])
    runtime_log = normalize_path(sys.argv[5])
    worker_log = normalize_path(sys.argv[6])

    pid_text = pid_file.read_text(encoding="utf-8", errors="ignore").strip() if pid_file.is_file() else ""
    running = pid_is_running(pid_text)

    if not running:
        for stale_path in (pid_file, lock_file):
            try:
                stale_path.unlink()
            except FileNotFoundError:
                pass
            except Exception:
                pass

    last_message = latest_db_log(db_path, user_id) or latest_runtime_log(runtime_log) or latest_worker_output(worker_log)
    data: dict[str, Any] = {"running": running, "last_message": last_message}
    if pid_text:
        try:
            data["pid"] = int(pid_text)
        except Exception:
            data["pid"] = pid_text
    emit(True, "Seat worker running" if running else "Seat worker not running", data)


if __name__ == "__main__":
    main()
