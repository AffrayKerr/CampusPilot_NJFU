#!/usr/bin/env bash
set -eu

script_dir=$(dirname "$0")
script_dir=$(cd "$script_dir" && pwd)
# shellcheck source=../auth/runtime.sh
source "$script_dir/../auth/runtime.sh"
SEAT_PYTHON=$(shell_auth_python)
# shellcheck source=../common/env.sh
source "$script_dir/../common/env.sh"
# shellcheck source=../common/response.sh
source "$script_dir/../common/response.sh"
# shellcheck source=../common/log.sh
source "$script_dir/../common/log.sh"

user_id="${1:-}"
seat_no="${2:-}"
floor="${3:-}"
reserve_date="${4:-}"
reserve_start_time="${5:-}"
reserve_end_time="${6:-}"
reserve_time_slots_json="${7:-[]}"

if [[ -z "$user_id" || -z "$seat_no" ]]; then
  shell_response_json false "Missing required parameters: user_id, seat_no"
  exit 1
fi

"$SEAT_PYTHON" "$script_dir/seat_client.py" reserve "$user_id" "$seat_no" "$floor" "$reserve_date" "$reserve_start_time" "$reserve_end_time" "$reserve_time_slots_json"
