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
export_path="${2:-}"

if [[ -z "$user_id" ]]; then
  shell_response_json false "user_id is required" null
  exit 1
fi

shell_db_init

uid_json="$(shell_db_query "SELECT id FROM users WHERE username = ? OR CAST(id AS TEXT) = ?" "$user_id" "$user_id")"
if [[ "$uid_json" == "[]" ]]; then
  shell_response_json false "user not found" null
  exit 1
fi

uid="$(echo "$uid_json" | "$AUTH_PYTHON" -c "import json, sys; d = json.load(sys.stdin); print(d[0]['id'] if d else '')")"

if [[ -z "$export_path" ]]; then
  user_dir="$(shell_env_ensure_user_runtime_dir "$user_id")"
  export_path="$user_dir/config_export_$(date +%Y%m%d_%H%M%S).json"
fi

shell_log_write INFO user "exporting user config" "user_id=$user_id export_path=$export_path" "$user_id"

result_json="$("$AUTH_PYTHON" - "$DATABASE_PATH" "$uid" "$export_path" <<'PY'
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

db_path = sys.argv[1]
uid = sys.argv[2]
export_path = Path(sys.argv[3])

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

export_data = {
    "version": "1.0",
    "exported_at": datetime.now().isoformat(),
    "notification_settings": {},
    "reminders": [],
    "seat_configs": [],
    "tasks": [],
}

ns = conn.execute("SELECT * FROM notification_settings WHERE user_id = ?", (uid,)).fetchone()
if ns:
    row = dict(ns)
    row.pop("id", None)
    row.pop("user_id", None)
    export_data["notification_settings"] = row

for r in conn.execute("SELECT * FROM reminders WHERE user_id = ?", (uid,)).fetchall():
    rd = dict(r)
    rd.pop("id", None)
    rd.pop("user_id", None)
    export_data["reminders"].append(rd)

for sc in conn.execute("SELECT * FROM seat_configs WHERE user_id = ?", (uid,)).fetchall():
    scd = dict(sc)
    scd.pop("id", None)
    scd.pop("user_id", None)
    export_data["seat_configs"].append(scd)

for t in conn.execute("SELECT * FROM tasks WHERE user_id = ?", (uid,)).fetchall():
    td = dict(t)
    td.pop("id", None)
    td.pop("user_id", None)
    export_data["tasks"].append(td)

conn.close()

export_path.parent.mkdir(parents=True, exist_ok=True)
export_path.write_text(json.dumps(export_data, ensure_ascii=False, indent=2), encoding="utf-8")

print(json.dumps({
    "export_path": str(export_path),
    "reminders_count": len(export_data["reminders"]),
    "seat_configs_count": len(export_data["seat_configs"]),
    "tasks_count": len(export_data["tasks"]),
}))
PY
)"

if [[ -z "$result_json" || "$result_json" != *'"export_path"'* ]]; then
  shell_log_write ERROR user "config export failed" "user_id=$user_id" "$user_id"
  shell_response_json false "Config export failed" null
  exit 1
fi

shell_log_write INFO user "config exported" "user_id=$user_id path=$export_path" "$user_id"
shell_response_json true "Config exported successfully" "$result_json"
