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

user_runtime_dir=$(shell_env_user_runtime_dir "$user_id")
lock_file="$user_runtime_dir/seat_worker.lock"
pid_file="$user_runtime_dir/seat_worker.pid"

if [[ ! -f "$pid_file" ]]; then
  shell_response_json false "Seat worker not running"
  exit 1
fi

pid=$(cat "$pid_file")
if ps -p "$pid" >/dev/null 2>&1; then
  kill "$pid" 2>/dev/null || true
  sleep 1
  if ps -p "$pid" >/dev/null 2>&1; then
    kill -9 "$pid" 2>/dev/null || true
  fi
fi

pkill -f "seat_client.py worker $user_id" 2>/dev/null || true
pkill -f "seat_worker.sh $user_id" 2>/dev/null || true

rm -f "$lock_file" "$pid_file"

shell_log_write "INFO" "seat" "Seat worker stopped" "pid=$pid" "$user_id"

shell_response_json true "Seat worker stopped" "{}"
