#!/usr/bin/env bash
set -eu

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
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

if [[ ! -f "$pid_file" ]]; then
  shell_response_json true "Seat worker not running" "{\"running\": false}"
  exit 0
fi

pid=$(cat "$pid_file")
if ps -p "$pid" >/dev/null 2>&1; then
  shell_response_json true "Seat worker running" "{\"running\": true, \"pid\": $pid}"
else
  shell_response_json true "Seat worker not running" "{\"running\": false}"
fi
