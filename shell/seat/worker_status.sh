#!/usr/bin/env bash
set -eu

script_dir=$(dirname "$0")
script_dir=$(cd "$script_dir" && pwd)
# shellcheck source=../common/env.sh
source "$script_dir/../common/env.sh"
# shellcheck source=../common/response.sh
source "$script_dir/../common/response.sh"

user_id="${1:-}"

if [[ -z "$user_id" ]]; then
  shell_response_json false "Missing required parameter: user_id"
  exit 1
fi

user_runtime_dir=$(shell_env_user_runtime_dir "$user_id")
pid_file="$user_runtime_dir/seat_worker.pid"
lock_file="$user_runtime_dir/seat_worker.lock"
log_file="$user_runtime_dir/seat_worker.log"

last_message=""
if [[ -f "$log_file" ]]; then
  while IFS= read -r line; do
    last_message="$line"
  done < "$log_file"
fi

emit_status() {
  local running="$1"
  local pid="${2:-}"
  "$(shell_response_python)" - "$running" "$pid" "$last_message" <<'PY'
import json
import sys
running = sys.argv[1].lower() == 'true'
pid = sys.argv[2]
last_message = sys.argv[3]
data = {"running": running, "last_message": last_message}
if pid:
    try:
        data["pid"] = int(pid)
    except ValueError:
        data["pid"] = pid
print(json.dumps({"success": True, "message": "Seat worker running" if running else "Seat worker not running", "data": data}, ensure_ascii=False))
PY
}

if [[ ! -f "$pid_file" ]]; then
  emit_status false
  exit 0
fi

pid=$(cat "$pid_file")
if ps -p "$pid" >/dev/null 2>&1; then
  emit_status true "$pid"
else
  rm -f "$pid_file" "$lock_file"
  emit_status false
fi
