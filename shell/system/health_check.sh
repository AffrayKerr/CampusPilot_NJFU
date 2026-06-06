#!/usr/bin/env bash
set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../common/env.sh"
source "$SCRIPT_DIR/../common/response.sh"
source "$SCRIPT_DIR/../common/db.sh"

shell_db_init

python3 - "$DATABASE_PATH" "$PROJECT_ROOT" "$USERS_RUNTIME_DIR" <<'PY'
import json
import os
import sqlite3
import sys
from pathlib import Path

db_path = Path(sys.argv[1])
project_root = Path(sys.argv[2])
users_runtime_dir = Path(sys.argv[3])

result = {
    "database": {"ok": False, "path": str(db_path), "size_bytes": 0},
    "directories": {},
    "active_workers": [],
    "log_size_bytes": 0,
}

if db_path.exists():
    result["database"]["ok"] = True
    result["database"]["size_bytes"] = db_path.stat().st_size
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("SELECT 1 FROM users LIMIT 1")
        conn.close()
    except Exception:
        result["database"]["ok"] = False

check_dirs = ["database", "logs", "runtime", "shell", "backend"]
for d in check_dirs:
    result["directories"][d] = (project_root / d).is_dir()

if users_runtime_dir.is_dir():
    for user_dir in users_runtime_dir.iterdir():
        pid_file = user_dir / "seat_worker.pid"
        if pid_file.exists():
            try:
                pid = int(pid_file.read_text().strip())
                os.kill(pid, 0)
                result["active_workers"].append({"user_id": user_dir.name, "pid": pid})
            except (OSError, ValueError):
                pass

log_dir = project_root / "logs"
if log_dir.is_dir():
    result["log_size_bytes"] = sum(
        f.stat().st_size for f in log_dir.rglob("*.log") if f.is_file()
    )

all_ok = result["database"]["ok"] and all(result["directories"].values())
print(json.dumps({
    "success": True,
    "message": "健康检查完成" if all_ok else "部分组件异常",
    "data": result
}, ensure_ascii=False))
PY
