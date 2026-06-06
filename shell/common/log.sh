#!/usr/bin/env bash
set -eu

# shellcheck source=./env.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/env.sh"

shell_log_write() {
  local level="${1:-INFO}"
  local module="${2:-system}"
  local message="${3:-}"
  local detail="${4:-}"
  local user_id="${5:-}"

  local log_file="$LOG_DIR/system.log"
  if [[ -n "$user_id" ]]; then
    local user_dir
    user_dir="$(shell_env_ensure_user_runtime_dir "$user_id")"
    log_file="$user_dir/runtime.log"
  else
    mkdir -p "$LOG_DIR"
  fi

  python - "$log_file" "$level" "$module" "$message" "$detail" "$DATABASE_PATH" "$user_id" <<'PY'
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

log_file   = Path(sys.argv[1])
level      = sys.argv[2]
module     = sys.argv[3]
message    = sys.argv[4]
detail     = sys.argv[5]
db_path    = sys.argv[6]
user_id_raw = sys.argv[7]  # username or numeric id string, may be empty

entry = {
    "timestamp": datetime.now().isoformat(),
    "level": level,
    "module": module,
    "message": message,
    "detail": detail,
}
log_file.parent.mkdir(parents=True, exist_ok=True)
with log_file.open('a', encoding='utf-8') as fh:
    fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

try:
    db = Path(db_path)
    if not db.exists():
        raise FileNotFoundError
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")

    uid = None
    if user_id_raw:
        row = conn.execute(
            "SELECT id FROM users WHERE CAST(id AS TEXT) = ? OR username = ?",
            (user_id_raw, user_id_raw),
        ).fetchone()
        if row:
            uid = row[0]

    conn.execute(
        "INSERT INTO logs (user_id, module, level, message, detail) VALUES (?, ?, ?, ?, ?)",
        (uid, module, level, message, detail),
    )
    conn.commit()
    conn.close()
except Exception:
    pass
PY
}
