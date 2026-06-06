#!/usr/bin/env bash
set -eu

script_dir=$(dirname "$0")
script_dir=$(cd "$script_dir" && pwd)
# shellcheck source=../auth/runtime.sh
source "$script_dir/../auth/runtime.sh"
SEAT_PYTHON=$(shell_auth_python)
# shellcheck source=../common/env.sh
source "$script_dir/../common/env.sh"
# shellcheck source=../common/db.sh
source "$script_dir/../common/db.sh"
# shellcheck source=../common/log.sh
source "$script_dir/../common/log.sh"

user_id="${1:-}"

if [[ -z "$user_id" ]]; then
  echo "Missing required parameter: user_id" >&2
  exit 1
fi

user_runtime_dir=$(shell_env_ensure_user_runtime_dir "$user_id")
pid_file="$user_runtime_dir/seat_worker.pid"
lock_file="$user_runtime_dir/seat_worker.lock"

shell_log_write "INFO" "seat" "Seat worker started" "" "$user_id"

trap 'shell_log_write "INFO" "seat" "Seat worker stopped by signal" "" "$user_id"; rm -f "$lock_file" "$pid_file"; exit 0' INT TERM

"$SEAT_PYTHON" "$script_dir/seat_client.py" worker "$user_id"

rm -f "$lock_file" "$pid_file"
