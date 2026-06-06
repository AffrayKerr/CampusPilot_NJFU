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
seat_no="${2:-}"
reserve_date="${3:-}"
reserve_start_time="${4:-}"
reserve_end_time="${5:-}"
reserve_time_slots_json="${6:-[]}"

if [[ -z "$user_id" || -z "$seat_no" ]]; then
  shell_response_json false "Missing required parameters: user_id, seat_no"
  exit 1
fi

python3 "$script_dir/seat_client.py" reserve "$user_id" "$seat_no" "$reserve_date" "$reserve_start_time" "$reserve_end_time" "$reserve_time_slots_json"
