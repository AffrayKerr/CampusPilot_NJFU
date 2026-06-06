#!/usr/bin/env bash
set -eu

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../common/env.sh
source "$script_dir/../common/env.sh"
# shellcheck source=../common/db.sh
source "$script_dir/../common/db.sh"
# shellcheck source=../common/response.sh
source "$script_dir/../common/response.sh"
# shellcheck source=../common/log.sh
source "$script_dir/../common/log.sh"

user_id="${1:-}"
floor="${2:-}"
seat_no="${3:-}"
priority="${4:-1}"
reserve_date="${5:-}"
reserve_start_time="${6:-}"
reserve_end_time="${7:-}"
check_start_time="${8:-}"
check_stop_time="${9:-}"
retry_interval="${10:-10}"
max_retry_count="${11:-30}"
max_duration_minutes="${12:-15}"
enabled="${13:-1}"
reserve_time_slots_json="${14:-[]}"

if [[ -z "$user_id" || -z "$seat_no" ]]; then
  shell_response_json false "Missing required parameters: user_id, seat_no"
  exit 1
fi

shell_db_execute \
  "INSERT INTO seat_configs (user_id, floor, seat_no, priority, reserve_date, reserve_start_time, reserve_end_time, reserve_time_slots, check_start_time, check_stop_time, retry_interval, max_retry_count, max_duration_minutes, enabled) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)" \
  "$user_id" "$floor" "$seat_no" "$priority" "$reserve_date" "$reserve_start_time" "$reserve_end_time" "$reserve_time_slots_json" "$check_start_time" "$check_stop_time" "$retry_interval" "$max_retry_count" "$max_duration_minutes" "$enabled"

config_id=$(shell_db_query "SELECT id FROM seat_configs WHERE user_id = ? ORDER BY id DESC LIMIT 1" "$user_id" | "$(shell_common_python)" -c "import sys, json; data=json.load(sys.stdin); print(data[0]['id'] if data else '')")

shell_log_write "INFO" "seat" "Seat config saved" "seat_no=$seat_no, priority=$priority" "$user_id"

shell_response_json true "Seat config saved" "{\"id\": $config_id, \"seat_no\": \"$seat_no\"}"
