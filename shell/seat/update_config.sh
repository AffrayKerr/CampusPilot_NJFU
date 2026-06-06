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
config_id="${2:-}"
floor="${3:-}"
seat_no="${4:-}"
priority="${5:-1}"
reserve_date="${6:-}"
reserve_start_time="${7:-}"
reserve_end_time="${8:-}"
check_start_time="${9:-}"
check_stop_time="${10:-}"
retry_interval="${11:-10}"
max_retry_count="${12:-30}"
max_duration_minutes="${13:-15}"
enabled="${14:-1}"
reserve_time_slots_json="${15:-[]}"

if [[ -z "$user_id" || -z "$config_id" || -z "$seat_no" ]]; then
  shell_response_json false "Missing required parameters: user_id, config_id, seat_no"
  exit 1
fi

shell_db_execute \
  "UPDATE seat_configs SET floor = ?, seat_no = ?, priority = ?, reserve_date = ?, reserve_start_time = ?, reserve_end_time = ?, reserve_time_slots = ?, check_start_time = ?, check_stop_time = ?, retry_interval = ?, max_retry_count = ?, max_duration_minutes = ?, enabled = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?" \
  "$floor" "$seat_no" "$priority" "$reserve_date" "$reserve_start_time" "$reserve_end_time" "$reserve_time_slots_json" "$check_start_time" "$check_stop_time" "$retry_interval" "$max_retry_count" "$max_duration_minutes" "$enabled" "$config_id" "$user_id"

shell_log_write "INFO" "seat" "Seat config updated" "config_id=$config_id, seat_no=$seat_no" "$user_id"

shell_response_json true "Seat config updated" "{\"id\": $config_id}"
