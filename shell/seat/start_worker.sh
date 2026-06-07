#!/usr/bin/env bash
set -eu

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../common/env.sh
source "$script_dir/../common/env.sh"
# shellcheck source=../common/response.sh
source "$script_dir/../common/response.sh"
# shellcheck source=../common/log.sh
source "$script_dir/../common/log.sh"

user_id="${1:-}"

if [[ -z "$user_id" ]]; then
  shell_response_json false "Missing required parameter: user_id"
  exit 1
fi

user_runtime_dir=$(shell_env_ensure_user_runtime_dir "$user_id")
lock_file="$user_runtime_dir/seat_worker.lock"
pid_file="$user_runtime_dir/seat_worker.pid"
log_file="$user_runtime_dir/seat_worker.log"

if [[ -f "$lock_file" ]] && [[ -f "$pid_file" ]]; then
  pid=$(cat "$pid_file")
  if ps -p "$pid" >/dev/null 2>&1; then
    shell_response_json false "Seat worker already running" "{\"pid\": $pid}"
    exit 1
  fi
fi

touch "$lock_file"
: > "$log_file"

nohup bash "$script_dir/seat_worker.sh" "$user_id" >> "$log_file" 2>&1 &
worker_pid=$!
echo "$worker_pid" > "$pid_file"

shell_log_write "INFO" "seat" "Seat worker started" "pid=$worker_pid" "$user_id"

shell_response_json true "Seat worker started" "{\"pid\": $worker_pid}"
