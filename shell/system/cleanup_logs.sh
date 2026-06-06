#!/usr/bin/env bash
set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../common/env.sh"
source "$SCRIPT_DIR/../common/response.sh"
source "$SCRIPT_DIR/../common/log.sh"
source "$SCRIPT_DIR/../common/db.sh"

keep_days="${1:-30}"

shell_db_init

deleted_db_rows=$(python3 - "$DATABASE_PATH" "$keep_days" <<'PY'
import sqlite3
import sys

db_path = sys.argv[1]
keep_days = int(sys.argv[2])

conn = sqlite3.connect(db_path)
conn.execute("PRAGMA foreign_keys = ON;")
cur = conn.execute(
    "DELETE FROM logs WHERE created_at < datetime('now', ? || ' days')",
    [f"-{keep_days}"],
)
deleted = cur.rowcount
conn.commit()
conn.close()
print(deleted)
PY
)

deleted_files=0
if [[ -d "$LOG_DIR" ]]; then
  while IFS= read -r -d '' log_file; do
    rm -f "$log_file"
    deleted_files=$((deleted_files + 1))
  done < <(find "$LOG_DIR" -name "*.log" -mtime +"$keep_days" -print0 2>/dev/null)
fi

shell_log_write INFO system "日志清理完成" "keep_days=$keep_days deleted_db_rows=$deleted_db_rows deleted_files=$deleted_files"
shell_response_json true "日志清理完成" "{\"keep_days\": $keep_days, \"deleted_db_rows\": $deleted_db_rows, \"deleted_files\": $deleted_files}"
