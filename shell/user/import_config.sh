#!/usr/bin/env bash
set -eu

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../auth/runtime.sh
source "$SCRIPT_DIR/../auth/runtime.sh"
AUTH_PYTHON="$(shell_auth_python)"
# shellcheck source=../common/env.sh
source "$SCRIPT_DIR/../common/env.sh"
# shellcheck source=../common/response.sh
source "$SCRIPT_DIR/../common/response.sh"
# shellcheck source=../common/log.sh
source "$SCRIPT_DIR/../common/log.sh"
# shellcheck source=../common/db.sh
source "$SCRIPT_DIR/../common/db.sh"

user_id="${1:-}"
import_path="${2:-}"

if [[ -z "$user_id" || -z "$import_path" ]]; then
  shell_response_json false "user_id and import_path are required" null
  exit 1
fi

if [[ ! -f "$import_path" ]]; then
  shell_response_json false "import file not found: $import_path" null
  exit 1
fi

shell_db_init

uid_json="$(shell_db_query "SELECT id FROM users WHERE username = ? OR CAST(id AS TEXT) = ?" "$user_id" "$user_id")"
if [[ "$uid_json" == "[]" ]]; then
  shell_response_json false "user not found" null
  exit 1
fi

uid="$(echo "$uid_json" | "$AUTH_PYTHON" -c "import json, sys; d = json.load(sys.stdin); print(d[0]['id'] if d else '')")"

shell_log_write INFO user "importing user config" "user_id=$user_id import_path=$import_path" "$user_id"

result_json="$("$AUTH_PYTHON" - "$DATABASE_PATH" "$uid" "$import_path" <<'PY' || true
import json
import sqlite3
import sys
from pathlib import Path

db_path = sys.argv[1]
uid = int(sys.argv[2])
import_path = Path(sys.argv[3])

try:
    import_data = json.loads(import_path.read_text(encoding="utf-8"))
except (json.JSONDecodeError, UnicodeDecodeError, FileNotFoundError) as e:
    print(json.dumps({"error": str(e)}))
    sys.exit(1)

conn = sqlite3.connect(db_path)
conn.execute("PRAGMA foreign_keys = ON;")
counts = {"notification_settings": 0, "reminders": 0, "seat_configs": 0, "tasks": 0}

try:
    ns = import_data.get("notification_settings")
    if ns:
        conn.execute("""
            INSERT OR REPLACE INTO notification_settings
            (user_id, enable_email, enable_desktop, enable_seat_result,
             enable_schedule_reminder, enable_error_alert,
             schedule_default_reminders, exam_default_reminders, task_default_reminders)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            uid,
            ns.get("enable_email", 0),
            ns.get("enable_desktop", 1),
            ns.get("enable_seat_result", 1),
            ns.get("enable_schedule_reminder", 1),
            ns.get("enable_error_alert", 1),
            ns.get("schedule_default_reminders", "[15]"),
            ns.get("exam_default_reminders", "[1440, 120]"),
            ns.get("task_default_reminders", "[1440, 120]"),
        ))
        counts["notification_settings"] = 1

    for r in import_data.get("reminders", []):
        conn.execute(
            "INSERT INTO reminders (user_id, target_type, target_id, remind_before_minutes, enabled)"
            " VALUES (?, ?, ?, ?, ?)",
            (uid, r["target_type"], r["target_id"], r["remind_before_minutes"], r.get("enabled", 1)),
        )
        counts["reminders"] += 1

    for sc in import_data.get("seat_configs", []):
        conn.execute("""
            INSERT INTO seat_configs
            (user_id, floor, seat_no, priority, reserve_date, reserve_start_time, reserve_end_time,
             reserve_time_slots, check_start_time, check_stop_time,
             retry_interval, max_retry_count, max_duration_minutes, enabled)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            uid,
            sc.get("floor"),
            sc["seat_no"],
            sc.get("priority", 1),
            sc.get("reserve_date"),
            sc.get("reserve_start_time"),
            sc.get("reserve_end_time"),
            sc.get("reserve_time_slots"),
            sc.get("check_start_time"),
            sc.get("check_stop_time"),
            sc.get("retry_interval", 10),
            sc.get("max_retry_count", 30),
            sc.get("max_duration_minutes", 15),
            sc.get("enabled", 1),
        ))
        counts["seat_configs"] += 1

    for t in import_data.get("tasks", []):
        conn.execute("""
            INSERT INTO tasks
            (user_id, title, category, priority, deadline,
             repeat_rule, reminder_time, note, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            uid,
            t["title"],
            t.get("category"),
            t.get("priority", "medium"),
            t["deadline"],
            t.get("repeat_rule"),
            t.get("reminder_time"),
            t.get("note"),
            t.get("status", "pending"),
        ))
        counts["tasks"] += 1

    conn.commit()
    conn.close()
    print(json.dumps(counts))

except Exception as e:
    conn.rollback()
    conn.close()
    print(json.dumps({"error": str(e)}))
    sys.exit(1)
PY
)"

if [[ -z "$result_json" || "$result_json" == *'"error"'* ]]; then
  err="$(echo "${result_json:-}" | "$AUTH_PYTHON" -c "import json,sys; d=json.loads(sys.stdin.read()); print(d.get('error','unknown'))" 2>/dev/null || echo "unknown")"
  shell_log_write ERROR user "config import failed" "user_id=$user_id error=$err" "$user_id"
  shell_response_json false "Config import failed: $err" null
  exit 1
fi

shell_log_write INFO user "config imported" "user_id=$user_id counts=$result_json" "$user_id"
shell_response_json true "Config imported successfully" "$result_json"
